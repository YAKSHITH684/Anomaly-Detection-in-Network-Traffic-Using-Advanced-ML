# utils/ml_utils.py
import io
import base64
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, f1_score
from joblib import dump, load
import matplotlib.pyplot as plt

def clean_columns(df):
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.replace(" ", "_")
        .str.lower()
    )
    return df

def preprocess_dataframe(df, label_col="attack_type"):
    df = df.copy()
    df = clean_columns(df)

    y = None
    y_le = None
    label_col = label_col.lower()

    if label_col in df.columns:
        y = df[label_col].astype(str)
        df = df.drop(columns=[label_col])

    cat_cols = df.select_dtypes(include=["object"]).columns
    num_cols = df.select_dtypes(include=["number"]).columns

    for c in num_cols:
        df[c] = df[c].fillna(df[c].median())

    for c in cat_cols:
        df[c] = df[c].fillna(df[c].mode().iloc[0])

    for c in cat_cols:
        le = LabelEncoder()
        df[c] = le.fit_transform(df[c].astype(str))

    if len(num_cols) > 0:
        df[num_cols] = StandardScaler().fit_transform(df[num_cols])

    if y is not None:
        y_le = LabelEncoder()
        y = y_le.fit_transform(y)

    return df, y, y_le

def train_and_evaluate_model(model_name, X_train, X_test, y_train, y_test):
    model_name = model_name.lower()

    if model_name == "naive_bayes":
        model = GaussianNB()
    elif model_name == "svm":
        model = SVC(probability=True)
    elif model_name == "random_forest":
        model = RandomForestClassifier()
    elif model_name == "logistic_regression":
        model = LogisticRegression(max_iter=1000)
    elif model_name == "xgboost":
        from xgboost import XGBClassifier
        model = XGBClassifier(eval_metric="logloss")
    elif model_name == "lightgbm":
        from lightgbm import LGBMClassifier
        model = LGBMClassifier()
    elif model_name == "isolation_forest":
        model = IsolationForest(contamination=0.1)
    else:
        raise ValueError("Unknown model")

    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "confusion_matrix": confusion_matrix(y_test, preds).tolist()
    }

    return metrics, model

def save_model(model, path):
    dump(model, path)

def load_model(path):
    return load(path)

def plot_accuracies(acc):
    plt.figure(figsize=(6,4))
    plt.bar(list(acc.keys()), list(acc.values()))
    plt.ylim(0,1)
    plt.title("Model Accuracies")
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
