# Retinopathy of Prematurity (ROP) Model Training & Deployment Guide

This guide describes how to train a compatible AI screening model and deploy the trained weights into the ROP AI Screener application.

---

## 1. Ethical & Regulatory Principles

> [!CAUTION]
> **Clinical Integrity Notice**:
> Retinopathy of Prematurity is a critical, sight-threatening condition affecting premature neonates. Artificial intelligence screening models must be developed using verified clinical datasets under Institutional Review Board (IRB) oversight and validated through clinical trials before any live patient deployment.
> 
> This project operates in **clearly labeled Demo Mode** when no validated model weights are installed. Never claim clinical diagnostic efficacy without rigorous real-world ophthalmological validation.

---

## 2. Dataset Preparation

Organize your dataset into the following directory structure:

```
dataset/
├── train/
│   ├── Normal/                  # Stage 0 / No ROP
│   ├── Pre-Plus/                # Pre-Plus or Mild ROP
│   └── Plus/                    # Plus disease or Severe ROP
└── val/
    ├── Normal/
    ├── Pre-Plus/
    └── Plus/
```

### Dataset Validation Requirements:
- **Image format**: Standard RGB retinal fundus images (`.jpg`, `.jpeg`, `.png`).
- **Minimum resolution**: At least 200×200 pixels (standard clinical fundus cameras typically provide 1500×1500 or higher).
- **Label format**: 3-class classification:
  1. `Normal` (Class 0)
  2. `Pre-Plus/Mild` (Class 1)
  3. `Plus Disease/Severe` (Class 2)

---

## 3. Dataset Pre-Validation

Before running training, run the dataset integrity checker to catch corrupted files, missing classes, or severe class imbalances:

```powershell
python backend/ml/train.py --data_dir "C:\path\to\dataset" --validate_only
```

Example output:
```
--- Dataset Validation Report ---
Total Valid Images: 1250
Corrupted/Low-Res:  0
Class Distribution: {'Normal': 800, 'Pre-Plus/Mild': 300, 'Plus Disease/Severe': 150}
---------------------------------
```

---

## 4. Training the Model

Run the training pipeline using the appropriate hardware:

```powershell
# Using CUDA GPU (Recommended for training)
python backend/ml/train.py `
  --data_dir "C:\path\to\dataset" `
  --output_path "backend/ml/weights/rop_model.pth" `
  --epochs 30 `
  --batch_size 16 `
  --lr 0.0001 `
  --device cuda

# Or using CPU for testing
python backend/ml/train.py `
  --data_dir "C:\path\to\dataset" `
  --output_path "backend/ml/weights/rop_model.pth" `
  --epochs 5 `
  --batch_size 8 `
  --device cpu
```

### Training Highlights:
- **Backbone**: EfficientNet-B0 pretrained on ImageNet.
- **Augmentation**: Random rotation, horizontal and vertical flips, color jitter tailored for fundus photography.
- **Optimization**: AdamW optimizer with Cosine Annealing learning rate schedule.
- **Checkpoints**: Automatically saves the checkpoint with the highest validation accuracy directly to `backend/ml/weights/rop_model.pth` along with `model_metadata.json`.

---

## 5. Installing Model Weights

To activate real model inference in the application:

1. Ensure your trained weights file is located at:
   ```
   backend/ml/weights/rop_model.pth
   ```
2. Restart the FastAPI backend server:
   ```powershell
   cd backend
   python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```
3. Check the startup logs:
   - When weights are detected:
     `INFO: Model weights found. AI inference is available.`
   - When weights are not present:
     `WARNING: DEMO MODE: No trained model found at backend/ml/weights/rop_model.pth. AI inference will return synthetic demonstration outputs.`
4. Verify via the API:
   ```powershell
   curl http://127.0.0.1:8000/api/health
   ```
   Output:
   ```json
   {
     "status": "healthy",
     "app_name": "ROP AI Screener",
     "version": "1.0.0-prototype",
     "demo_mode": false,
     "model_available": true
   }
   ```
