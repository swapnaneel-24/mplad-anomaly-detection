# ============================================================
# PHASE 3: Evaluation & IF vs LOF Comparison (Amended)
# ============================================================
import pandas as pd
import numpy as np
import pickle
import gc
import os
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, confusion_matrix

# 1. Load ground truth labels
print("Loading ground truth...")
CSV_PATH = "/content/drive/MyDrive/mplad-dvc-storage/creditcard_preprocessed.csv"

df = pd.read_csv(CSV_PATH)
y = df['Class']

# 2. Define Evaluation Function
def evaluate_model(pred_dict, y_true):
    results = []
    for name, data in pred_dict.items():
        labels = data['labels']
        scores = data['scores']
        
        # Both iForest decision_function and LOF negative_outlier_factor_ 
        # format scores such that LOWER = MORE ANOMALOUS.
        # We invert them so HIGHER = MORE ANOMALOUS for AUC metrics.
        scores_auc = -scores
            
        prec = precision_score(y_true, labels, zero_division=0)
        rec = recall_score(y_true, labels, zero_division=0)
        f1 = f1_score(y_true, labels, zero_division=0)
        roc = roc_auc_score(y_true, scores_auc)
        pr_auc = average_precision_score(y_true, scores_auc)
        
        tn, fp, fn, tp = confusion_matrix(y_true, labels, labels=[0, 1]).ravel()
        
        results.append({
            'Combo': name,
            'Precision': round(prec, 4),
            'Recall': round(rec, 4),
            'F1': round(f1, 4),
            'ROC_AUC': round(roc, 4),
            'PR_AUC': round(pr_auc, 4),
            'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn
        })
    return pd.DataFrame(results)

# 3. Evaluate Isolation Forest (Load, Eval, Delete)
print("Loading & evaluating iForest predictions...")

# Point directly to the file inside your permanent Google Drive folder
IF_PKL_PATH = "/content/drive/MyDrive/mplad-dvc-storage/iforest_raw_predictions.pkl"

with open(IF_PKL_PATH, "rb") as f:
    if_preds = pickle.load(f)

if_eval_df = evaluate_model(if_preds, y)
if_eval_df['Model'] = 'IsolationForest'


# Extract best IF config and labels before deleting the dict
best_if_row = if_eval_df.sort_values(by='F1', ascending=False).iloc[0]
best_if_name = best_if_row['Combo']
best_if_labels = if_preds[best_if_name]['labels']

del if_preds
gc.collect()

# 4. Evaluate LOF (Load, Eval, Delete)
print("Loading & evaluating LOF predictions...")

# FIX: Use the LOF_PKL_PATH variable that points directly to your Google Drive
LOF_PKL_PATH = os.path.join(STORAGE_DIR, "iforest_raw_predictions.pkl")

with open(LOF_PKL_PATH, "rb") as f:
    lof_preds = pickle.load(f)

lof_eval_df = evaluate_model(lof_preds, y)
lof_eval_df['Model'] = 'LOF'

# Extract best LOF config and labels before deleting the dict
best_lof_row = lof_eval_df.sort_values(by='F1', ascending=False).iloc[0]
best_lof_name = best_lof_row['Combo']
best_lof_labels = lof_preds[best_lof_name]['labels']

del lof_preds
gc.collect()

# 5. Combine and Save Master Metrics
master_eval_df = pd.concat([if_eval_df, lof_eval_df], ignore_index=True)
master_eval_df.to_csv("phase3_evaluation_metrics.csv", index=False)

# 6. Display Best Performers
print("\n=== BEST ISOLATION FOREST CONFIGURATION ===")
print(best_if_row[['Combo', 'Precision', 'Recall', 'F1', 'ROC_AUC', 'PR_AUC', 'TP', 'FP']])

print("\n=== BEST LOF CONFIGURATION ===")
print(best_lof_row[['Combo', 'Precision', 'Recall', 'F1', 'ROC_AUC', 'PR_AUC', 'TP', 'FP']])

# 7. Anomaly Overlap / Consistency
overlap = np.sum((best_if_labels == 1) & (best_lof_labels == 1))
total_flagged = np.sum(best_if_labels) + np.sum(best_lof_labels)
jaccard_similarity = overlap / (total_flagged - overlap) if (total_flagged - overlap) > 0 else 0

print("\n=== ANOMALY OVERLAP (Best IF vs Best LOF) ===")
print(f"IF flagged: {np.sum(best_if_labels)} | LOF flagged: {np.sum(best_lof_labels)}")
print(f"Commonly flagged (Overlap): {overlap}")
print(f"Jaccard Similarity (Agreement): {round(jaccard_similarity, 4)}")