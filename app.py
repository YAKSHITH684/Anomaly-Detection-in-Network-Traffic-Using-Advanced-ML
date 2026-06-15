# # app.py
# from flask import Flask, request, redirect, url_for, render_template, session, flash
# import os
# import pandas as pd
# import io, base64, traceback
# import matplotlib
# matplotlib.use('Agg')
# import matplotlib.pyplot as plt
# import seaborn as sns

# from sklearn.model_selection import train_test_split
# from sklearn.preprocessing import StandardScaler, LabelEncoder
# from sklearn.metrics import (
#     accuracy_score, precision_score, recall_score, f1_score,
#     confusion_matrix
# )
# from sklearn.naive_bayes import GaussianNB
# from sklearn.linear_model import LogisticRegression
# from sklearn.svm import SVC
# from sklearn.ensemble import RandomForestClassifier

# import joblib

# # Optional models
# try:
#     import xgboost as xgb
#     HAS_XGB = True
# except:
#     HAS_XGB = False

# try:
#     import lightgbm as lgb
#     HAS_LGB = True
# except:
#     HAS_LGB = False

# # Optional SMOTE
# try:
#     from imblearn.over_sampling import SMOTE
#     HAS_SMOTE = True
# except:
#     HAS_SMOTE = False

# app = Flask(__name__)
# app.secret_key = "super-secret-key"

# UPLOAD_FOLDER = "uploads"
# MODEL_FOLDER = "models"
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# os.makedirs(MODEL_FOLDER, exist_ok=True)

# # Logs
# if 'LOGS' not in app.config:
#     app.config['LOGS'] = []

# def add_log(msg):
#     app.config['LOGS'].insert(0, msg)
#     if len(app.config['LOGS']) > 200:
#         app.config['LOGS'] = app.config['LOGS'][:200]

# # Dataset store
# DATA_STORE = {
#     "df": None,
#     # after preprocess/split
#     "X_train": None, "X_test": None,
#     "y_train": None, "y_test": None,
#     # scaler used after one-hot (for numeric features)
#     "scaler": None,
#     # training feature columns after get_dummies
#     "feature_columns": None,
#     # target label encoder
#     "target_encoder": None
# }

# #################################
# # Helpers
# #################################

# def allowed_file(filename):
#     return "." in filename and filename.rsplit(".", 1)[1].lower() == "csv"

# def plot_to_base64(fig):
#     buf = io.BytesIO()
#     fig.savefig(buf, format='png', bbox_inches='tight')
#     buf.seek(0)
#     encoded = base64.b64encode(buf.read()).decode('utf-8')
#     plt.close(fig)
#     return encoded

# def compute_metrics(y_true, y_pred):
#     return {
#         "accuracy": accuracy_score(y_true, y_pred),
#         "precision": precision_score(y_true, y_pred, average='weighted', zero_division=0),
#         "recall": recall_score(y_true, y_pred, average='weighted', zero_division=0),
#         "f1": f1_score(y_true, y_pred, average='weighted', zero_division=0)
#     }

# #################################
# # Preprocessing (one-hot + scaling)
# #################################

# def preprocess_df(df):
#     """
#     - Drops duplicates
#     - Fill missing (numeric: median, object: mode)
#     - Expects 'attack_type' as target
#     - Uses pd.get_dummies for categorical variables (drop_first=False to keep all dummy columns)
#     - Returns: X_df (pandas DataFrame with all features numeric), y_enc (ndarray), scaler (fitted), target_le
#     """
#     df = df.copy()

#     # Drop duplicates
#     before = df.shape[0]
#     df = df.drop_duplicates()
#     after = df.shape[0]
#     add_log(f"Dropped {before-after} duplicate rows.")

#     # Fill missing
#     for col in df.columns:
#         if df[col].dtype == "O":
#             mode = df[col].mode()
#             if not mode.empty:
#                 df[col] = df[col].fillna(mode[0])
#             else:
#                 df[col] = df[col].fillna("unknown")
#         else:
#             df[col] = df[col].fillna(df[col].median())

#     if "attack_type" not in df.columns:
#         raise Exception("Dataset must contain 'attack_type' column.")

#     # Separate target
#     y = df["attack_type"].astype(str).copy()
#     X = df.drop(columns=["attack_type"]).copy()

#     # One-hot encode categorical features
#     # Use get_dummies to create binary columns for categories (this avoids artificial ordering)
#     X_dummies = pd.get_dummies(X, drop_first=False)

#     # Fit scaler to the whole X_dummies (scales numeric-like columns; dummy columns are 0/1 so scaling is okay)
#     scaler = StandardScaler()
#     X_scaled = scaler.fit_transform(X_dummies.values)
#     X_scaled_df = pd.DataFrame(X_scaled, columns=X_dummies.columns)

#     # Encode target labels
#     target_le = LabelEncoder()
#     y_enc = target_le.fit_transform(y)

#     add_log(f"One-hot encoded features: {len(X_dummies.columns)} columns. Classes: {list(target_le.classes_)}")

#     return X_scaled_df, y_enc, scaler, target_le

# #################################
# # Routes
# #################################

# @app.route("/")
# def root():
#     return redirect(url_for("login"))

# @app.route("/login", methods=["GET", "POST"])
# def login():
#     DEMO_USER = {"username": "admin", "password": "admin123"}

#     if request.method == "POST":
#         username = request.form.get("username", "").strip()
#         password = request.form.get("password", "").strip()

#         if username == DEMO_USER["username"] and password == DEMO_USER["password"]:
#             session["username"] = username
#             add_log(f"{username} logged in.")
#             return redirect(url_for("dashboard"))
#         else:
#             flash("Invalid credentials.")
#             return render_template("login.html")

#     return render_template("login.html")

# @app.route("/dashboard")
# def dashboard():
#     if "username" not in session:
#         flash("Please login first.")
#         return redirect(url_for("login"))

#     preview_html = None
#     df = DATA_STORE["df"]
#     if df is not None:
#         preview_html = df.head().to_html(classes="table table-striped", index=False)

#     return render_template(
#         "dashboard.html",
#         logs=app.config['LOGS'],
#         preview_html=preview_html,
#         title="Main Dashboard"
#     )

# @app.route("/upload", methods=["POST"])
# def upload():
#     if "username" not in session:
#         flash("Please login first.")
#         return redirect(url_for("login"))

#     file = request.files.get("file")

#     if not file or not allowed_file(file.filename):
#         flash("Please upload a valid CSV file.")
#         return redirect(url_for("dashboard"))

#     try:
#         filepath = os.path.join(UPLOAD_FOLDER, file.filename)
#         file.save(filepath)

#         df = pd.read_csv(filepath)
#         DATA_STORE["df"] = df

#         add_log(f"Uploaded: {file.filename} (Shape: {df.shape})")

#         return redirect(url_for("dashboard"))

#     except Exception as e:
#         add_log("Upload Error: " + str(e))
#         add_log(traceback.format_exc())
#         flash("Failed to read CSV. Check logs.")
#         return redirect(url_for("dashboard"))

# @app.route("/preprocess", methods=["POST"])
# def preprocess():
#     if DATA_STORE["df"] is None:
#         flash("Upload dataset first.")
#         return redirect(url_for("dashboard"))

#     try:
#         df = DATA_STORE["df"]
#         X_df, y_arr, scaler, target_le = preprocess_df(df)

#         # Train/test split (stratify to keep class ratios)
#         X_train_df, X_test_df, y_train, y_test = train_test_split(
#             X_df, y_arr, test_size=0.2, random_state=42, stratify=y_arr
#         )

#         # Apply SMOTE on training set if available
#         if HAS_SMOTE:
#             try:
#                 sm = SMOTE(random_state=42)
#                 X_train_res, y_train_res = sm.fit_resample(X_train_df.values, y_train)
#                 # convert back to DataFrame with same columns
#                 X_train_df = pd.DataFrame(X_train_res, columns=X_train_df.columns)
#                 y_train = y_train_res
#                 add_log("Applied SMOTE to training set.")
#             except Exception as e:
#                 add_log("SMOTE failed: " + str(e))
#                 add_log(traceback.format_exc())
#                 flash("SMOTE failed; continuing without SMOTE.")
#         else:
#             add_log("imblearn.SMOTE not available; skipping SMOTE. (install imbalanced-learn to enable)")

#         # Keep scaler and feature columns for later prediction alignment
#         DATA_STORE.update({
#             "X_train": X_train_df.values,
#             "X_test": X_test_df.values,
#             "y_train": y_train,
#             "y_test": y_test,
#             "scaler": scaler,
#             "feature_columns": list(X_df.columns),
#             "target_encoder": target_le
#         })

#         add_log(f"Preprocessing OK | Train: {X_train_df.shape} Test: {X_test_df.shape}")
#         flash("Preprocessing completed.")

#     except Exception as e:
#         add_log("Preprocessing Error: " + str(e))
#         add_log(traceback.format_exc())
#         flash("Preprocessing failed. Check logs.")

#     return redirect(url_for("dashboard"))

# @app.route("/train/<model_name>")
# def train(model_name):
#     if DATA_STORE["X_train"] is None:
#         flash("Run preprocessing first.")
#         return redirect(url_for("dashboard"))

#     X_train, X_test = DATA_STORE["X_train"], DATA_STORE["X_test"]
#     y_train, y_test = DATA_STORE["y_train"], DATA_STORE["y_test"]

#     try:
#         # Select model with class weighting where helpful
#         if model_name == "naive_bayes":
#             clf = GaussianNB()
#         elif model_name == "logistic":
#             clf = LogisticRegression(max_iter=2000, class_weight='balanced')
#         elif model_name == "svm":
#             clf = SVC(probability=True, class_weight='balanced')
#         elif model_name == "random_forest":
#             clf = RandomForestClassifier(n_estimators=200, class_weight='balanced')
#         elif model_name == "xgboost":
#             if not HAS_XGB:
#                 flash("XGBoost not installed.")
#                 return redirect(url_for("dashboard"))
#             # xgboost handles imbalance via scale_pos_weight in binary; for multiclass we rely on parameters and balanced sampling
#             clf = xgb.XGBClassifier(eval_metric='mlogloss', use_label_encoder=False, n_estimators=200)
#         elif model_name == "lightgbm":
#             if not HAS_LGB:
#                 flash("LightGBM not installed.")
#                 return redirect(url_for("dashboard"))
#             clf = lgb.LGBMClassifier(n_estimators=200)
#         else:
#             flash("Unknown model.")
#             return redirect(url_for("dashboard"))

#         add_log(f"Training model: {model_name} ...")
#         # Fit: X arrays are numpy arrays stored earlier
#         clf.fit(X_train, y_train)

#         preds = clf.predict(X_test)
#         metrics = compute_metrics(y_test, preds)
#         cm = confusion_matrix(y_test, preds)

#         add_log(f"Accuracy: {metrics['accuracy']:.4f}")
#         add_log(f"Precision: {metrics['precision']:.4f}")
#         add_log(f"Recall: {metrics['recall']:.4f}")
#         add_log(f"F1 Score: {metrics['f1']:.4f}")
#         add_log(f"Confusion Matrix: \n{cm}")

#         # Save Model
#         model_path = os.path.join(MODEL_FOLDER, f"{model_name}.joblib")
#         joblib.dump({
#             "model": clf,
#             "feature_columns": DATA_STORE["feature_columns"],
#             "scaler": DATA_STORE["scaler"],
#             "target_encoder": DATA_STORE["target_encoder"]
#         }, model_path)

#         # Save Metrics
#         if "model_metrics" not in session:
#             session["model_metrics"] = {}
#         session["model_metrics"][model_name] = metrics

#         # Save confusion matrix image for quick viewing
#         try:
#             fig = plt.figure(figsize=(5,4))
#             sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
#             plt.title(f'Confusion Matrix: {model_name}')
#             b64 = plot_to_base64(fig)
#             app.config.setdefault('last_confusion', {})[model_name] = b64
#         except:
#             add_log("Failed to save confusion matrix image.")

#         flash(f"Training finished: {model_name}")

#     except Exception as e:
#         add_log("Training Error: " + str(e))
#         add_log(traceback.format_exc())
#         flash("Training failed.")

#     return redirect(url_for("dashboard"))

# @app.route("/graphs")
# def graphs():
#     model_metrics = session.get("model_metrics", {})
#     if not model_metrics:
#         flash("Train some models first.")
#         return redirect(url_for("dashboard"))

#     names = list(model_metrics.keys())
#     accs = [model_metrics[m]["accuracy"] for m in names]

#     # Bar Chart
#     fig1 = plt.figure(figsize=(6,4))
#     sns.barplot(x=names, y=accs)
#     plt.ylim(0,1)
#     plt.title("Model Accuracies")
#     acc_img = plot_to_base64(fig1)

#     # Pie Chart
#     fig2 = plt.figure(figsize=(5,5))
#     plt.pie(accs, labels=names, autopct="%1.1f%%")
#     plt.title("Model Contribution")
#     pie_img = plot_to_base64(fig2)

#     return render_template("graphs.html", acc_img=acc_img, pie_img=pie_img)

# @app.route("/predict", methods=["POST"])
# def predict():
#     file = request.files.get("file")
#     if not file or not allowed_file(file.filename):
#         flash("Upload valid CSV.")
#         return redirect(url_for("dashboard"))

#     # pick best model
#     model_metrics = session.get("model_metrics", {})
#     if not model_metrics:
#         flash("Train at least one model.")
#         return redirect(url_for("dashboard"))

#     best_model = max(model_metrics.items(), key=lambda x: x[1]["accuracy"])[0]
#     model_path = os.path.join(MODEL_FOLDER, f"{best_model}.joblib")

#     try:
#         saved = joblib.load(model_path)
#         clf = saved["model"]
#         feature_columns = saved.get("feature_columns") or DATA_STORE.get("feature_columns")
#         scaler = saved.get("scaler") or DATA_STORE.get("scaler")
#         target_le = saved.get("target_encoder") or DATA_STORE.get("target_encoder")

#         df = pd.read_csv(file)

#         # if target present in uploaded file, drop it (we predict)
#         if "attack_type" in df.columns:
#             df = df.drop(columns=["attack_type"])

#         # One-hot encode incoming features the same way: use get_dummies then align columns
#         incoming = pd.get_dummies(df, drop_first=False)

#         # Reindex to training feature columns; add missing cols with 0
#         if feature_columns is None:
#             flash("Feature columns metadata missing; cannot align features.")
#             return redirect(url_for("dashboard"))

#         # ensure all expected columns exist
#         incoming_aligned = incoming.reindex(columns=feature_columns, fill_value=0)

#         # scale using saved scaler
#         X_test_scaled = scaler.transform(incoming_aligned.values)

#         preds = clf.predict(X_test_scaled)

#         if target_le is not None:
#             pred_labels = target_le.inverse_transform(preds)
#         else:
#             pred_labels = preds.astype(str)

#         out_df = df.copy()
#         out_df["prediction"] = pred_labels
#         table_html = out_df.head(200).to_html(classes="table table-striped", index=False)

#         add_log(f"Prediction OK using {best_model}. (rows: {len(preds)})")

#         return render_template(
#             "predict_result.html",
#             table_html=table_html,
#             model_name=best_model
#         )

#     except Exception as e:
#         add_log("Prediction Error: " + str(e))
#         add_log(traceback.format_exc())
#         flash("Prediction failed.")
#         return redirect(url_for("dashboard"))

# @app.route("/cm/<model_name>")
# def cm_view(model_name):
#     cm_dict = app.config.get('last_confusion', {})
#     b64 = cm_dict.get(model_name)
#     if not b64:
#         flash("No confusion matrix image for this model.")
#         return redirect(url_for('dashboard'))
#     return f'<img src="data:image/png;base64,{b64}"/>'

# @app.route("/logout")
# def logout():
#     session.clear()
#     flash("Logged out.")
#     return redirect(url_for("login"))

# #################################
# # MAIN
# #################################

# if __name__ == "__main__":
#     app.run(debug=True, port=5000)


# app.py
from flask import Flask, request, redirect, url_for, render_template, session, flash
import os
import pandas as pd
import io, base64, traceback
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier

import joblib

# Optional models
try:
    import xgboost as xgb
    HAS_XGB = True
except:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except:
    HAS_LGB = False

# Optional SMOTE
try:
    from imblearn.over_sampling import SMOTE
    HAS_SMOTE = True
except:
    HAS_SMOTE = False

app = Flask(__name__)
app.secret_key = "super-secret-key"

UPLOAD_FOLDER = "uploads"
MODEL_FOLDER = "models"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MODEL_FOLDER, exist_ok=True)

# Logs
if 'LOGS' not in app.config:
    app.config['LOGS'] = []

def add_log(msg):
    app.config['LOGS'].insert(0, msg)
    if len(app.config['LOGS']) > 200:
        app.config['LOGS'] = app.config['LOGS'][:200]

# Dataset store
DATA_STORE = {
    "df": None,
    # after preprocess/split
    "X_train": None, "X_test": None,
    "y_train": None, "y_test": None,
    # scaler used after one-hot (for numeric features)
    "scaler": None,
    # training feature columns after get_dummies
    "feature_columns": None,
    # target label encoder
    "target_encoder": None
}

#################################
# Helpers
#################################

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "csv"

def plot_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return encoded

def compute_accuracy(y_true, y_pred):
    return accuracy_score(y_true, y_pred)

def aggregated_confusion_summary(cm: np.ndarray):
    """
    Aggregate multiclass confusion into 4 numbers (D1 style):
    TP = sum of diagonal (correct predictions)
    FP = total - TP   (all wrong predictions)
    FN = total - TP   (same as FP in this simple aggregated view)
    TN = 0
    Returns dict with TP, FP, FN, TN, total
    """
    total = int(cm.sum())
    tp = int(np.trace(cm))
    fp = total - tp
    fn = total - tp
    tn = 0
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "total": total}

#################################
# Preprocessing (one-hot + scaling)
#################################

def preprocess_df(df):
    """
    - Drops duplicates
    - Fill missing (numeric: median, object: mode)
    - Expects 'attack_type' as target
    - Uses pd.get_dummies for categorical variables (drop_first=False to keep all dummy columns)
    - Returns: X_df (pandas DataFrame with all features numeric), y_enc (ndarray), scaler (fitted), target_le
    """
    df = df.copy()

    # Drop duplicates
    before = df.shape[0]
    df = df.drop_duplicates()
    after = df.shape[0]
    add_log(f"Dropped {before-after} duplicate rows.")

    # Fill missing
    for col in df.columns:
        if df[col].dtype == "O":
            mode = df[col].mode()
            if not mode.empty:
                df[col] = df[col].fillna(mode[0])
            else:
                df[col] = df[col].fillna("unknown")
        else:
            df[col] = df[col].fillna(df[col].median())

    if "attack_type" not in df.columns:
        raise Exception("Dataset must contain 'attack_type' column.")

    # Separate target
    y = df["attack_type"].astype(str).copy()
    X = df.drop(columns=["attack_type"]).copy()

    # One-hot encode categorical features
    X_dummies = pd.get_dummies(X, drop_first=False)

    # Fit scaler to the whole X_dummies
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_dummies.values)
    X_scaled_df = pd.DataFrame(X_scaled, columns=X_dummies.columns)

    # Encode target labels
    target_le = LabelEncoder()
    y_enc = target_le.fit_transform(y)

    add_log(f"One-hot encoded features: {len(X_dummies.columns)} columns. Classes: {list(target_le.classes_)}")

    return X_scaled_df, y_enc, scaler, target_le

#################################
# Routes
#################################

@app.route("/")
def root():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    DEMO_USER = {"username": "admin", "password": "admin123"}

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == DEMO_USER["username"] and password == DEMO_USER["password"]:
            session["username"] = username
            add_log(f"{username} logged in.")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials.")
            return render_template("login.html")

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    preview_html = None
    df = DATA_STORE["df"]
    if df is not None:
        preview_html = df.head().to_html(classes="table table-striped", index=False)

    return render_template(
        "dashboard.html",
        logs=app.config['LOGS'],
        preview_html=preview_html,
        title="Main Dashboard"
    )

@app.route("/upload", methods=["POST"])
def upload():
    if "username" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    file = request.files.get("file")

    if not file or not allowed_file(file.filename):
        flash("Please upload a valid CSV file.")
        return redirect(url_for("dashboard"))

    try:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        df = pd.read_csv(filepath)
        DATA_STORE["df"] = df

        add_log(f"Uploaded: {file.filename} (Shape: {df.shape})")

        return redirect(url_for("dashboard"))

    except Exception as e:
        add_log("Upload Error: " + str(e))
        add_log(traceback.format_exc())
        flash("Failed to read CSV. Check logs.")
        return redirect(url_for("dashboard"))

@app.route("/preprocess", methods=["POST"])
def preprocess():
    if DATA_STORE["df"] is None:
        flash("Upload dataset first.")
        return redirect(url_for("dashboard"))

    try:
        df = DATA_STORE["df"]
        X_df, y_arr, scaler, target_le = preprocess_df(df)

        # Train/test split (stratify to keep class ratios)
        X_train_df, X_test_df, y_train, y_test = train_test_split(
            X_df, y_arr, test_size=0.2, random_state=42, stratify=y_arr
        )

        # Apply SMOTE on training set if available
        if HAS_SMOTE:
            try:
                sm = SMOTE(random_state=42)
                X_train_res, y_train_res = sm.fit_resample(X_train_df.values, y_train)
                # convert back to DataFrame with same columns
                X_train_df = pd.DataFrame(X_train_res, columns=X_train_df.columns)
                y_train = y_train_res
                add_log("Applied SMOTE to training set.")
            except Exception as e:
                add_log("SMOTE failed: " + str(e))
                add_log(traceback.format_exc())
                flash("SMOTE failed; continuing without SMOTE.")
        else:
            add_log("imblearn.SMOTE not available; skipping SMOTE. (install imbalanced-learn to enable)")

        # Keep scaler and feature columns for later prediction alignment
        DATA_STORE.update({
            "X_train": X_train_df.values,
            "X_test": X_test_df.values,
            "y_train": y_train,
            "y_test": y_test,
            "scaler": scaler,
            "feature_columns": list(X_df.columns),
            "target_encoder": target_le
        })

        add_log(f"Preprocessing OK | Train: {X_train_df.shape} Test: {X_test_df.shape}")
        flash("Preprocessing completed.")

    except Exception as e:
        add_log("Preprocessing Error: " + str(e))
        add_log(traceback.format_exc())
        flash("Preprocessing failed. Check logs.")

    return redirect(url_for("dashboard"))

@app.route("/train/<model_name>")
def train(model_name):
    if DATA_STORE["X_train"] is None:
        flash("Run preprocessing first.")
        return redirect(url_for("dashboard"))

    X_train, X_test = DATA_STORE["X_train"], DATA_STORE["X_test"]
    y_train, y_test = DATA_STORE["y_train"], DATA_STORE["y_test"]

    try:
        # Select model with class weighting where helpful
        if model_name == "naive_bayes":
            clf = GaussianNB()
        elif model_name == "logistic":
            clf = LogisticRegression(max_iter=2000, class_weight='balanced')
        elif model_name == "svm":
            clf = SVC(probability=True, class_weight='balanced')
        elif model_name == "random_forest":
            clf = RandomForestClassifier(n_estimators=200, class_weight='balanced')
        elif model_name == "xgboost":
            if not HAS_XGB:
                flash("XGBoost not installed.")
                return redirect(url_for("dashboard"))
            clf = xgb.XGBClassifier(eval_metric='mlogloss', use_label_encoder=False, n_estimators=200)
        elif model_name == "lightgbm":
            if not HAS_LGB:
                flash("LightGBM not installed.")
                return redirect(url_for("dashboard"))
            clf = lgb.LGBMClassifier(n_estimators=200)
        else:
            flash("Unknown model.")
            return redirect(url_for("dashboard"))

        add_log(f"Training model: {model_name} ...")
        clf.fit(X_train, y_train)

        preds = clf.predict(X_test)

        # compute only accuracy
        accuracy = compute_accuracy(y_test, preds)
        cm = confusion_matrix(y_test, preds)

        # aggregated confusion summary (D1)
        agg = aggregated_confusion_summary(cm)

        add_log(f"Accuracy: {accuracy:.4f}")
        add_log("Confusion Matrix (Aggregated):")
        add_log(f"TP: {agg['TP']}")
        add_log(f"FP: {agg['FP']}")
        add_log(f"FN: {agg['FN']}")
        add_log(f"TN: {agg['TN']}")

        # Save Model (with metadata)
        model_path = os.path.join(MODEL_FOLDER, f"{model_name}.joblib")
        joblib.dump({
            "model": clf,
            "feature_columns": DATA_STORE["feature_columns"],
            "scaler": DATA_STORE["scaler"],
            "target_encoder": DATA_STORE["target_encoder"]
        }, model_path)

        # Save only accuracy in session metrics
        if "model_metrics" not in session:
            session["model_metrics"] = {}
        session["model_metrics"][model_name] = {"accuracy": float(accuracy)}

        # Save (full) confusion matrix image (for reference) but no longer required for aggregated display
        try:
            fig = plt.figure(figsize=(5,4))
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
            plt.title(f'Confusion Matrix (full) - {model_name}')
            b64 = plot_to_base64(fig)
            app.config.setdefault('last_confusion', {})[model_name] = b64
        except Exception:
            add_log("Failed to save confusion matrix image.")

        flash(f"Training finished: {model_name}")

    except Exception as e:
        add_log("Training Error: " + str(e))
        add_log(traceback.format_exc())
        flash("Training failed.")

    return redirect(url_for("dashboard"))

@app.route("/graphs")
def graphs():
    model_metrics = session.get("model_metrics", {})
    if not model_metrics:
        flash("Train some models first.")
        return redirect(url_for("dashboard"))

    names = list(model_metrics.keys())
    accs = [model_metrics[m]["accuracy"] for m in names]

    # Bar Chart
    fig1 = plt.figure(figsize=(6,4))
    sns.barplot(x=names, y=accs)
    plt.ylim(0,1)
    plt.title("Model Accuracies")
    acc_img = plot_to_base64(fig1)

    # Pie Chart
    fig2 = plt.figure(figsize=(5,5))
    plt.pie(accs, labels=names, autopct="%1.1f%%")
    plt.title("Model Contribution")
    pie_img = plot_to_base64(fig2)

    return render_template("graphs.html", acc_img=acc_img, pie_img=pie_img)

@app.route("/predict", methods=["POST"])
def predict():
    file = request.files.get("file")
    if not file or not allowed_file(file.filename):
        flash("Upload valid CSV.")
        return redirect(url_for("dashboard"))

    model_metrics = session.get("model_metrics", {})
    if not model_metrics:
        flash("Train at least one model.")
        return redirect(url_for("dashboard"))

    best_model = max(model_metrics.items(), key=lambda x: x[1]["accuracy"])[0]
    model_path = os.path.join(MODEL_FOLDER, f"{best_model}.joblib")

    try:
        saved = joblib.load(model_path)
        clf = saved["model"]
        feature_columns = saved.get("feature_columns") or DATA_STORE.get("feature_columns")
        scaler = saved.get("scaler") or DATA_STORE.get("scaler")
        target_le = saved.get("target_encoder") or DATA_STORE.get("target_encoder")

        df = pd.read_csv(file)

        # if target present in uploaded file, drop it (we predict)
        if "attack_type" in df.columns:
            df = df.drop(columns=["attack_type"])

        # One-hot encode incoming features then align
        incoming = pd.get_dummies(df, drop_first=False)

        if feature_columns is None:
            flash("Feature columns metadata missing; cannot align features.")
            return redirect(url_for("dashboard"))

        incoming_aligned = incoming.reindex(columns=feature_columns, fill_value=0)

        # scale using saved scaler
        X_test_scaled = scaler.transform(incoming_aligned.values)

        preds = clf.predict(X_test_scaled)

        if target_le is not None:
            pred_labels = target_le.inverse_transform(preds)
        else:
            pred_labels = preds.astype(str)

        out_df = df.copy()
        out_df["prediction"] = pred_labels
        table_html = out_df.head(200).to_html(classes="table table-striped", index=False)

        add_log(f"Prediction OK using {best_model}. (rows: {len(preds)})")

        return render_template(
            "predict_result.html",
            table_html=table_html,
            model_name=best_model
        )

    except Exception as e:
        add_log("Prediction Error: " + str(e))
        add_log(traceback.format_exc())
        flash("Prediction failed.")
        return redirect(url_for("dashboard"))

@app.route("/cm/<model_name>")
def cm_view(model_name):
    cm_dict = app.config.get('last_confusion', {})
    b64 = cm_dict.get(model_name)
    if not b64:
        flash("No confusion matrix image for this model.")
        return redirect(url_for('dashboard'))
    return f'<img src="data:image/png;base64,{b64}"/>'

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("login"))

#################################
# MAIN
#################################

if __name__ == "__main__":
    app.run(debug=True, port=5000)

