"""
Phase 6 - Train Graph Neural Network (GNN)
=====================================================================
Builds a Graph from the training dataset where:
  - Nodes = Drugs
  - Node Features = Morgan Fingerprints (2048-dim)
  - Edges = Known drug-drug interactions

Trains a GraphSAGE or GCN model to predict links (interactions) 
between drugs. Evaluates on the Standard Test and Zero-Shot Test sets.

Outputs:
    models/gnn_model.pt
    results/gnn_metrics.csv

Usage:
    python src/06_train_gnn.py
"""

import os
import json
import torch
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv, SAGEConv
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, accuracy_score, precision_score, recall_score
import numpy as np
import pandas as pd
from tqdm import tqdm

SPLIT_DIR   = os.path.join("data", "splits")
PROC_DIR    = os.path.join("data", "processed")
MODEL_DIR   = "models"
RESULTS_DIR = "results"

RANDOM_SEED = 42
torch.manual_seed(RANDOM_SEED)

# Hyperparameters
HIDDEN_CHANNELS = 128
EPOCHS = 100
LR = 0.001
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


# ─────────────────────────────────────────────
# 1. GNN Model Definition (Link Prediction)
# ─────────────────────────────────────────────
class GNN(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels):
        super().__init__()
        # Using GraphSAGE as it generally performs better for this kind of task
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, hidden_channels)
        self.conv3 = SAGEConv(hidden_channels, out_channels)

    def encode(self, x, edge_index):
        # Generate node embeddings
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index).relu()
        x = self.conv3(x, edge_index)
        return x

    def decode(self, z, edge_label_index):
        # Predict edge existence (dot product of node embeddings)
        return (z[edge_label_index[0]] * z[edge_label_index[1]]).sum(dim=-1)

    def decode_all(self, z):
        prob_adj = z @ z.t()
        return (prob_adj > 0).nonzero(as_tuple=False).t()


# ─────────────────────────────────────────────
# 2. Graph Construction
# ─────────────────────────────────────────────
def build_graph():
    print("[Graph] Building the drug interaction graph...")
    
    # 1. Load the SMILES to get mapping of all drugs
    smiles_df = pd.read_csv(os.path.join(PROC_DIR, "drug_smiles.csv"))
    drug_to_idx = {drug: i for i, drug in enumerate(smiles_df['drug'])}
    num_nodes = len(drug_to_idx)
    print(f"  Total unique drugs (nodes): {num_nodes}")

    # 2. Re-compute node features (Morgan Fingerprints)
    # We load it from features.npz but we need it per-drug, not per-pair
    # To save time in this script, we'll reconstruct them from the SMILES cache
    from rdkit import Chem
    from rdkit.Chem import AllChem, DataStructs
    
    node_features = np.zeros((num_nodes, 2048), dtype=np.float32)
    for drug, row in smiles_df.iterrows():
        idx = drug_to_idx[row['drug']]
        smiles = row['smiles']
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
                arr = np.zeros((2048,), dtype=np.float32)
                DataStructs.ConvertToNumpyArray(fp, arr)
                node_features[idx] = arr
        except Exception:
            pass # Keep as all zeros if failed
            
    x = torch.tensor(node_features, dtype=torch.float)
    print(f"  Node features shape: {x.shape}")

    # 3. Build edges from TRAINING set only
    train_pairs = pd.read_csv(os.path.join(SPLIT_DIR, "train_pairs.csv"))
    train_y = np.load(os.path.join(SPLIT_DIR, "train_y.npy"))
    
    # Only use positive interactions to build the graph topology!
    pos_train = train_pairs[train_y == 1]
    
    edge_index = []
    for _, row in pos_train.iterrows():
        if row['drug1'] in drug_to_idx and row['drug2'] in drug_to_idx:
            u = drug_to_idx[row['drug1']]
            v = drug_to_idx[row['drug2']]
            edge_index.append([u, v])
            edge_index.append([v, u]) # undirected
            
    edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
    print(f"  Training edges (undirected): {edge_index.shape[1]}")

    # Create PyG Data object
    data = Data(x=x, edge_index=edge_index)
    
    # 4. Create supervision edges for train/test/zs
    def create_supervision_edges(split_name):
        pairs = pd.read_csv(os.path.join(SPLIT_DIR, f"{split_name}_pairs.csv"))
        y = np.load(os.path.join(SPLIT_DIR, f"{split_name}_y.npy"))
        
        edges = []
        valid_y = []
        for i, row in pairs.iterrows():
            if row['drug1'] in drug_to_idx and row['drug2'] in drug_to_idx:
                edges.append([drug_to_idx[row['drug1']], drug_to_idx[row['drug2']]])
                valid_y.append(y[i])
                
        return torch.tensor(edges, dtype=torch.long).t().contiguous(), torch.tensor(valid_y, dtype=torch.float)

    print("  Creating supervision labels...")
    data.train_pos_edge_index, data.train_y = create_supervision_edges("train")
    data.test_pos_edge_index, data.test_y = create_supervision_edges("test")
    data.zs_pos_edge_index, data.zs_y = create_supervision_edges("zeroshot")
    
    return data

# ─────────────────────────────────────────────
# 3. Training and Evaluation
# ─────────────────────────────────────────────
def train(model, optimizer, criterion, data):
    model.train()
    optimizer.zero_grad()
    
    # Embed all nodes using the message passing graph (only positive train edges)
    z = model.encode(data.x, data.edge_index)
    
    # Predict on the supervision edges (both positive and negative train edges)
    out = model.decode(z, data.train_pos_edge_index)
    
    loss = criterion(out, data.train_y)
    loss.backward()
    optimizer.step()
    return loss.item()

@torch.no_grad()
def test(model, data, edge_label_index, y_true, split_name):
    model.eval()
    z = model.encode(data.x, data.edge_index)
    out = model.decode(z, edge_label_index)
    
    # Apply sigmoid for probabilities
    y_pred_proba = torch.sigmoid(out).cpu().numpy()
    y_pred = (y_pred_proba > 0.5).astype(int)
    y_true_np = y_true.cpu().numpy()
    
    return {
        "Model": "GNN (GraphSAGE)",
        "Split": split_name,
        "AUC-ROC": roc_auc_score(y_true_np, y_pred_proba),
        "AUC-PR": average_precision_score(y_true_np, y_pred_proba),
        "F1": f1_score(y_true_np, y_pred),
        "Precision": precision_score(y_true_np, y_pred),
        "Recall": recall_score(y_true_np, y_pred),
        "Accuracy": accuracy_score(y_true_np, y_pred)
    }

def main():
    print("=" * 60)
    print("  DDI Research - Phase 6: Train GNN")
    print("=" * 60)
    print(f"  Using device: {DEVICE}")
    
    ensure_dir(MODEL_DIR)
    ensure_dir(RESULTS_DIR)

    # 1. Build Graph
    try:
        data = build_graph()
        data = data.to(DEVICE)
    except FileNotFoundError as e:
        print(f"ERROR: Missing files. {e}")
        print("Ensure Phase 3 (Featurize) and Phase 4 (Split) are completed.")
        return

    # 2. Setup Model
    model = GNN(in_channels=data.num_features, 
                hidden_channels=HIDDEN_CHANNELS, 
                out_channels=64).to(DEVICE)
                
    optimizer = torch.optim.Adam(params=model.parameters(), lr=LR)
    criterion = torch.nn.BCEWithLogitsLoss()

    # 3. Train Loop
    print("\n[Train] Starting GNN training...")
    best_val_auc = 0
    pbar = tqdm(range(1, EPOCHS + 1))
    
    for epoch in pbar:
        loss = train(model, optimizer, criterion, data)
        
        # We use test set as validation here for simplicity of demonstration, 
        # in a strict setup you'd use the val set
        if epoch % 10 == 0:
            res = test(model, data, data.test_pos_edge_index, data.test_y, "val")
            pbar.set_description(f"Epoch {epoch:03d} | Loss: {loss:.4f} | Test AUC: {res['AUC-ROC']:.4f}")
            
    # 4. Final Evaluation
    print("\n[Eval] Running final evaluation...")
    res_test = test(model, data, data.test_pos_edge_index, data.test_y, "Standard Test")
    res_zs = test(model, data, data.zs_pos_edge_index, data.zs_y, "Zero-Shot Test")
    
    all_results = [res_test, res_zs]
    
    # Save Model
    model_path = os.path.join(MODEL_DIR, "gnn_model.pt")
    torch.save(model.state_dict(), model_path)
    print(f"  Saved model to {model_path}")
    
    # Save Results
    results_df = pd.DataFrame(all_results)
    out_csv = os.path.join(RESULTS_DIR, "gnn_metrics.csv")
    
    # Append to classical if exists, else create new
    classical_csv = os.path.join(RESULTS_DIR, "classical_metrics.csv")
    if os.path.exists(classical_csv):
        classical_df = pd.read_csv(classical_csv)
        final_df = pd.concat([classical_df, results_df], ignore_index=True)
        final_df.to_csv(os.path.join(RESULTS_DIR, "final_comparison.csv"), index=False)
        print(f"  Appended to classical results and saved final_comparison.csv")
    else:
        results_df.to_csv(out_csv, index=False)
        print(f"  Saved {out_csv}")

    print("\n" + "=" * 60)
    print("  TRAINING SUMMARY (GNN)")
    print("=" * 60)
    print(results_df.to_string(index=False))
    print(f"\nNext step: python src/07_evaluate.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
