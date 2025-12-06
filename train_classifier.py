#!/usr/bin/env python3
"""
Multi-Class Classification Model for IaC Code Quality
Predicts code quality in 5 categories based on Maintainability Index (MI):
- Poor: MI < 40
- Needs Work: 40 <= MI < 55
- Acceptable: 55 <= MI < 70
- Good: 70 <= MI < 85
- Exceptional: MI >= 85

Compares Logistic Regression vs Random Forest
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)
import argparse
import warnings

warnings.filterwarnings("ignore")


def load_and_prepare_data(csv_file):
    """Load dataset and prepare features/target."""
    print(f"Loading dataset from {csv_file}...")
    df = pd.read_csv(csv_file)

    # Filter out file summaries - we want block-level analysis
    df = df[df["block_type"] != "FILE_SUMMARY"]
    print(f"  Loaded {len(df)} code blocks")

    # Create 5-category target based on MI ranges (aligned with MI interpretation table)
    def categorize_quality(mi):
        if mi < 40:
            return 0  # Poor
        elif mi < 55:
            return 1  # Needs Work
        elif mi < 70:
            return 2  # Acceptable
        elif mi < 85:
            return 3  # Good
        else:
            return 4  # Exceptional

    df["quality_category"] = df["maintainability_index"].apply(categorize_quality)

    # Print distribution
    category_names = [
        "Poor (0-39)",
        "Needs Work (40-54)",
        "Acceptable (55-69)",
        "Good (70-84)",
        "Exceptional (85-100)"
    ]
    print("\nQuality Distribution:")
    for i, name in enumerate(category_names):
        count = (df["quality_category"] == i).sum()
        print(f"  {name}: {count} ({count/len(df)*100:.1f}%)")

    return df


def select_features(df):
    """Select relevant features for training."""
    # TerraMetric features
    tm_features = [col for col in df.columns if col.startswith("tm_")]

    # Block-level features
    block_features = ["loc"]

    # GitHub features (if available)
    gh_features = [col for col in df.columns if col.startswith("gh_")]

    all_features = tm_features + block_features + gh_features

    # Filter to only existing columns with numeric data
    available_features = []
    for feat in all_features:
        if feat in df.columns:
            try:
                df[feat].fillna(0).astype(float)
                available_features.append(feat)
            except (ValueError, TypeError):
                continue

    print(f"\nUsing {len(available_features)} features:")
    for feat in sorted(available_features):
        print(f"  - {feat}")

    return available_features


def train_logistic_regression(X_train, y_train, X_test, y_test):
    """Train and evaluate Logistic Regression."""
    print("\n" + "=" * 80)
    print("LOGISTIC REGRESSION (Multi-Class)")
    print("=" * 80)

    # Scale features (important for LR)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train model (multi-class)
    lr = LogisticRegression(
        max_iter=1000,
        random_state=42,
        class_weight="balanced",
        multi_class="multinomial"
    )
    lr.fit(X_train_scaled, y_train)

    # Predictions
    y_pred = lr.predict(X_test_scaled)

    # Evaluate
    print_metrics(y_test, y_pred)

    # Feature importance (average absolute coefficient across all classes)
    print("\nTop 10 Most Important Features (by average absolute coefficient):")
    avg_coef = np.mean(np.abs(lr.coef_), axis=0)
    feature_importance = pd.DataFrame(
        {"feature": X_train.columns, "coefficient": avg_coef}
    ).sort_values("coefficient", ascending=False)

    for idx, row in feature_importance.head(10).iterrows():
        print(f"  {row['feature']:<30} {row['coefficient']:>10.4f}")

    return lr, scaler


def train_random_forest(X_train, y_train, X_test, y_test):
    """Train and evaluate Random Forest."""
    print("\n" + "=" * 80)
    print("RANDOM FOREST (Multi-Class)")
    print("=" * 80)

    # Train model
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1
    )
    rf.fit(X_train, y_train)

    # Predictions
    y_pred = rf.predict(X_test)

    # Evaluate
    print_metrics(y_test, y_pred)

    # Feature importance
    print("\nTop 10 Most Important Features (by Gini importance):")
    feature_importance = pd.DataFrame(
        {"feature": X_train.columns, "importance": rf.feature_importances_}
    ).sort_values("importance", ascending=False)

    for idx, row in feature_importance.head(10).iterrows():
        print(f"  {row['feature']:<30} {row['importance']:>10.4f}")

    return rf


def print_metrics(y_test, y_pred):
    """Print classification metrics for multi-class."""
    print(f"\nAccuracy:  {accuracy_score(y_test, y_pred):.4f}")
    print(f"Macro Avg Precision: {precision_score(y_test, y_pred, average='macro', zero_division=0):.4f}")
    print(f"Macro Avg Recall:    {recall_score(y_test, y_pred, average='macro', zero_division=0):.4f}")
    print(f"Macro Avg F1 Score:  {f1_score(y_test, y_pred, average='macro', zero_division=0):.4f}")
    print(f"Weighted Avg F1:     {f1_score(y_test, y_pred, average='weighted', zero_division=0):.4f}")

    print("\nConfusion Matrix:")
    # Get all unique labels that appear in y_test or y_pred
    labels = sorted(list(set(y_test) | set(y_pred)))
    cm = confusion_matrix(y_test, y_pred, labels=labels)

    # Print header
    print(f"{'':>20}", end="")
    print("Predicted")
    print(f"{'':>20}", end="")
    for label in labels:
        print(f"{label:>6}", end="")
    print()

    # Print rows
    category_labels_all = ["Poor", "Needs Work", "Acceptable", "Good", "Exceptional"]
    for i, label in enumerate(labels):
        if i == 0:
            print(f"{'Actual':>8} {label} ({category_labels_all[label]:<11})", end="")
        else:
            print(f"{'':>8} {label} ({category_labels_all[label]:<11})", end="")
        for j in range(len(labels)):
            print(f"{cm[i][j]:>6}", end="")
        print()

    print("\nClassification Report:")
    all_target_names = [
        "Poor (0)",
        "Needs Work (1)",
        "Acceptable (2)",
        "Good (3)",
        "Exceptional (4)"
    ]
    # Only use target names for labels that actually appear
    target_names = [all_target_names[label] for label in labels]
    print(classification_report(y_test, y_pred, labels=labels, target_names=target_names, zero_division=0))


def compare_models(lr_metrics, rf_metrics):
    """Compare both models side by side."""
    print("\n" + "=" * 80)
    print("MODEL COMPARISON")
    print("=" * 80)

    print(f"\n{'Metric':<25} {'Logistic Regression':<25} {'Random Forest':<25}")
    print("-" * 75)

    metrics = ["Accuracy", "Macro Precision", "Macro Recall", "Macro F1", "Weighted F1"]
    for metric in metrics:
        lr_val = lr_metrics.get(metric, 0)
        rf_val = rf_metrics.get(metric, 0)
        winner = "←" if lr_val > rf_val else ("→" if rf_val > lr_val else "=")
        print(f"{metric:<25} {lr_val:>20.4f} {winner:^3} {rf_val:>20.4f}")


def main():
    parser = argparse.ArgumentParser(description="Train IaC quality classification models (5 categories)")
    parser.add_argument(
        "--input",
        type=str,
        default="output/iac_dataset.csv",
        help="Input CSV dataset file",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Test set size (default: 0.2)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("IaC CODE QUALITY CLASSIFICATION (5 CATEGORIES)")
    print("=" * 80)

    # Load and prepare data
    df = load_and_prepare_data(args.input)

    # Select features
    feature_cols = select_features(df)

    # Prepare X and y
    X = df[feature_cols].fillna(0)
    y = df["quality_category"]

    # Check for class imbalance
    class_counts = y.value_counts(normalize=True).sort_index()
    min_class_pct = class_counts.min() * 100
    if min_class_pct < 10:
        print(f"\n⚠️  Warning: Class imbalance detected (smallest class: {min_class_pct:.1f}%)")
        print("   Using class_weight='balanced' to handle imbalance")

    # Split data
    print(f"\nSplitting data: {int((1-args.test_size)*100)}% train, {int(args.test_size*100)}% test")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y
    )
    print(f"  Training set: {len(X_train)} samples")
    print(f"  Test set:     {len(X_test)} samples")

    # Train Logistic Regression
    lr_model, scaler = train_logistic_regression(X_train, y_train, X_test, y_test)

    # Extract LR metrics
    X_test_scaled = scaler.transform(X_test)
    lr_pred = lr_model.predict(X_test_scaled)
    lr_metrics = {
        "Accuracy": accuracy_score(y_test, lr_pred),
        "Macro Precision": precision_score(y_test, lr_pred, average='macro'),
        "Macro Recall": recall_score(y_test, lr_pred, average='macro'),
        "Macro F1": f1_score(y_test, lr_pred, average='macro'),
        "Weighted F1": f1_score(y_test, lr_pred, average='weighted'),
    }

    # Train Random Forest
    rf_model = train_random_forest(X_train, y_train, X_test, y_test)

    # Extract RF metrics
    rf_pred = rf_model.predict(X_test)
    rf_metrics = {
        "Accuracy": accuracy_score(y_test, rf_pred),
        "Macro Precision": precision_score(y_test, rf_pred, average='macro'),
        "Macro Recall": recall_score(y_test, rf_pred, average='macro'),
        "Macro F1": f1_score(y_test, rf_pred, average='macro'),
        "Weighted F1": f1_score(y_test, rf_pred, average='weighted'),
    }

    # Compare models
    compare_models(lr_metrics, rf_metrics)

    # Recommendation
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if rf_metrics["Weighted F1"] > lr_metrics["Weighted F1"] + 0.02:
        print("\n✓ Random Forest performs better overall")
        print("  - Better at capturing non-linear relationships")
        print("  - Higher weighted F1 score across all 5 categories")
        print("  - Recommended for production use")
    elif lr_metrics["Weighted F1"] > rf_metrics["Weighted F1"] + 0.02:
        print("\n✓ Logistic Regression performs better overall")
        print("  - More interpretable (linear coefficients)")
        print("  - Faster inference time")
        print("  - Recommended for production use")
    else:
        print("\n≈ Both models perform similarly")
        print("  - Use Logistic Regression for interpretability")
        print("  - Use Random Forest for slightly better predictions")

    print("\n" + "=" * 80)
    print("\nQuality Categories (aligned with MI interpretation table):")
    print("  0 = Poor:        MI 0-39")
    print("  1 = Needs Work:  MI 40-54")
    print("  2 = Acceptable:  MI 55-69")
    print("  3 = Good:        MI 70-84")
    print("  4 = Exceptional: MI 85-100")
    print("=" * 80)


if __name__ == "__main__":
    main()
