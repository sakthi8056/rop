# ROP AI Screener

An AI-assisted Retinopathy of Prematurity (ROP) screening application designed to assist healthcare professionals in neonatal intensive care units (NICUs) and rural health centers.

---

## Key Features

- **Patient Registration**: Capture infant demographics, gestational age (weeks + days), birth weight, and clinical history.
- **Retinal Image Quality Assessment**: Multi-point automated checks for image sharpness/blur (Laplacian variance), illumination, contrast, resolution, and aspect ratio before analysis.
- **AI Screening & Transparent Demo Mode**:
  - **With Trained Weights**: EfficientNet-B0 classifier identifies *Normal*, *Pre-Plus/Mild*, or *Plus Disease/Severe*.
  - **Without Trained Weights (Current State)**: Operates in a clearly labeled **Demo Mode** (`is_demo: true`, fixed non-fabricated baseline outputs, prominent clinical warning banners on UI and reports).
- **Explainable AI (XAI)**: Generates Grad-CAM visual attention heatmaps (or geometric demonstration overlays in demo mode) highlighting key vascular structures.
- **Clinical Protocol Recommendations**: Maps screening classifications to actionable follow-up urgencies (Routine, Elevated, Urgent, or Manual Specialist Review).
- **Bilingual Screening Reports**: Instant report generation in **English** and **Tamil** with automated PDF export (with graceful styled HTML preview & download fallback).
- **Screening History**: Filter and review past screening sessions by patient ID, status, and date range.

---

## Architecture & Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **Database**: SQLite with async support (`aiosqlite`)
- **Authentication**: JWT (JSON Web Tokens) with direct `bcrypt` password hashing
- **Image Processing**: OpenCV Headless & Pillow
- **Reports**: Jinja2 templating with optional WeasyPrint engine (HTML fallback for universal Windows offline support)
- **AI/ML Engine**: PyTorch & torchvision (EfficientNet-B0 architecture)

### Frontend
- **Framework**: React 19 with Vite
- **Routing**: React Router v7
- **Localization**: `react-i18next` (English / தமிழ்)
- **Icons**: Lucide React
- **Styling**: Vanilla CSS Medical Design System

---

## Quick Start on Windows

### Prerequisites
- **Python**: Version 3.10 through 3.14 (pre-configured in the project virtual environment)
- **Node.js**: Version 18 or higher
- **PowerShell** or Command Prompt

---

### 1. Running the Backend Server

Open a PowerShell terminal and navigate to the project directory:

```powershell
cd c:\sakthi_rop\backend

# Run using the project virtual environment
..\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

> **Backend Endpoints:**
> - API Base URL: `http://127.0.0.1:8000`
> - Swagger UI (Interactive API Docs): `http://127.0.0.1:8000/docs`
> - Health Check: `http://127.0.0.1:8000/api/health`

#### Default Admin Credentials
When the database is first initialized, the default user is seeded:
- **Username**: `admin`
- **Password**: `rop2024`
- **Role**: `doctor`

---

### 2. Running the Frontend Web Application

Open a second PowerShell terminal:

```powershell
cd c:\sakthi_rop\frontend

# Install dependencies (if not already installed)
npm install

# Start development server
npm run dev
```

> **Frontend Web App:**
> - Open your browser at: `http://localhost:5173`
> - Log in using `admin` / `rop2024`.

---

## AI Model Architecture, Real Inference & Demo Mode

### Root Cause Analysis of Previous Model Loading Failure
During the project audit, the model was failing to load due to five specific factors:
1. **Uninstalled Dependencies**: `torch`, `torchvision`, and `grad-cam` were commented out in `requirements.txt` and were not installed in the active environment.
2. **Missing Weights**: The weights directory `backend/ml/weights/` was empty (`rop_model.pth` was missing).
3. **Loader Caching Bug (`backend/ml/model_loader.py`)**: When checked without weights, the loader cached `_model_loaded = True`, permanently locking the server into demo mode even after weights were later supplied.
4. **Class Index Mismatch (`backend/ml/train.py`)**: PyTorch's `ImageFolder` sorts directory names alphabetically (`0: Normal`, `1: Plus`, `2: Pre-Plus`), whereas the canonical medical ontology in `config.py` is `0: Normal`, `1: Pre-Plus/Mild`, `2: Plus Disease/Severe`. This silently swapped classes 1 and 2!
5. **Transform Distortion**: Fundus photos were stretched to `(256, 256)` rather than preserving aspect ratio before center-cropping.

All five issues have been resolved. The deep learning dependencies are installed, loader caching is fixed, a canonical `ROPDataset` enforces explicit index mapping (`Normal: 0`, `Pre-Plus: 1`, `Plus: 2`), and aspect-preserving preprocessing is synchronized.

---

### Dual Operating Modes

| Feature | Real Model Mode (`rop_model.pth` present) | Demo Mode (No weights file installed) |
| :--- | :--- | :--- |
| **Model Status** | `demo_mode: false`, `model_available: true` | `demo_mode: true`, `model_available: false` |
| **Predictions** | Real neural network classification (`Normal`, `Pre-Plus/Mild`, `Plus Disease/Severe`) | Synthetic fixed baseline label: `DEMO — No Real Model Loaded` |
| **Confidence** | Real softmax probability (e.g. `94.3%`) | Explicitly `null` / `None` (no fabricated numbers) |
| **Probabilities** | Real 3-class distribution summing to `1.0` | Fixed `0.00%` across all classes |
| **Explainability** | Real Grad-CAM heatmap generated by backpropagation | Geometric demonstration overlay labeled "DEMO" |
| **UI Badges** | Clean medical report with clinical limitations disclaimer | High-visibility warning banner: `⚠️ DEMO MODE ACTIVE` |

---

## Public ROP Datasets & Training Workflow

### 1. Legitimate Public Datasets

For training and research validation, use verified, open-access neonatal retinal imaging collections:

1. **FARFUM-RoP (Fundus Images from Neonates for ROP Classification)**:
   - **Scale**: 1,533 retinal fundus images from 68 preterm neonates.
   - **Labels**: 3-class annotations (`Normal`, `Pre-Plus`, `Plus Disease`).
   - **Repository**: Figshare Open Access ([DOI: 10.6084/m9.figshare.24075593](https://doi.org/10.6084/m9.figshare.24075593))
2. **Macretina ROP Dataset**:
   - **Scale**: 1,432 expert-annotated retinal fundus images.
   - **Repository**: Figshare ([Link](https://figshare.com/articles/dataset/Macretina_A_dataset_to_support_deep_learning_assisted_Retinopathy_of_Prematurity_diagnosis/24513812))
3. **Kaggle ROP Collections**:
   - E.g., `zohaibaslam03/augmented-dataset` or search `Retinopathy of Prematurity`.
4. **ROP-VL Dataset**:
   - Multimodal fundus images and clinical texts ([DOI: 10.6084/m9.figshare.27137350](https://doi.org/10.6084/m9.figshare.27137350)).

To print full dataset reference links at any time:
```powershell
.venv\Scripts\python backend/ml/dataset_downloader.py --info
```

---

### 2. Organizing Raw Downloaded Datasets

Once you download an archive from Figshare or Kaggle, organize it into the canonical structure using the dataset utility:

```powershell
.venv\Scripts\python backend/ml/dataset_downloader.py `
  --organize `
  --source "C:\path\to\downloaded_extracted_folder" `
  --output "data/rop_dataset"
```

The script automatically detects folder synonyms (`Normal`, `Pre-Plus`, `Mild`, `Plus`, `Severe`), validates readability, and creates balanced `train/` and `val/` splits.

---

### 3. Validating Dataset Integrity

Before training, run pre-validation to detect corrupt images, unsupported formats, or low-resolution scans:

```powershell
.venv\Scripts\python backend/ml/train.py --data_dir "data/rop_dataset" --validate_only
```

---

### 4. Reproducible Model Training

Train the EfficientNet-B0 backbone with cosine annealing learning rate schedule and canonical class mapping:

```powershell
# Using CUDA GPU (Recommended for clinical training)
.venv\Scripts\python backend/ml/train.py `
  --data_dir "data/rop_dataset" `
  --output_path "backend/ml/weights/rop_model.pth" `
  --epochs 25 `
  --batch_size 16 `
  --lr 0.0001 `
  --device cuda

# Or using CPU for testing / development
.venv\Scripts\python backend/ml/train.py `
  --data_dir "data/rop_dataset" `
  --output_path "backend/ml/weights/rop_model.pth" `
  --epochs 5 `
  --batch_size 8 `
  --device cpu
```

The script automatically:
- Preserves aspect ratios and applies fundus-specific augmentations.
- Enforces canonical class indexing (`Normal: 0`, `Pre-Plus: 1`, `Plus: 2`).
- Saves the best checkpoint to `backend/ml/weights/rop_model.pth`.
- Exports training metrics and hyperparameters to `backend/ml/weights/model_metadata.json`.

---

## Running the Automated Test Suite

From the project root (`c:\sakthi_rop`):

```powershell
# Run backend pytest suite (19 test cases)
.venv\Scripts\python -m pytest backend/tests -v

# Run end-to-end clinical workflow verification script
.venv\Scripts\python backend/verify_runtime.py

# Run frontend linting & production build
cd frontend
npm run build
```

---

## Report Generation & Tamil Fonts

- **Tamil Font Rendering**: Report templates include font fallbacks for native Windows Indic fonts (`NotoSansTamil`, `Nirmala UI`, and `Latha`).
- **PDF Engine**: Direct PDF generation uses WeasyPrint. On Windows systems where native GTK3 C-libraries are not installed, the application automatically falls back to generating printable, high-fidelity HTML reports without crashing or throwing server errors.

---

## Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `Cannot connect to API` in frontend | Backend is not running on port 8000 | Ensure backend is started in Terminal 1 at `http://127.0.0.1:8000`. |
| `Login failed: Invalid credentials` | Using outdated password | Use username `admin` and password `rop2024`. |
| `Model not loading` / stuck in Demo Mode | Weights file missing or corrupted | Run `backend/ml/train.py` or place a valid `.pth` at `backend/ml/weights/rop_model.pth`. Verify via `/api/health`. |
| `No module named torch` | Deep learning dependencies not installed | Run `& .venv\Scripts\python -m pip install -r backend/requirements.txt`. |
| `Port 8000 already in use` | Another instance of uvicorn is running | Kill the existing process: `Get-Process python \| Stop-Process` or change the port using `--port 8001`. |

---

## Clinical Disclaimer & Known Limitations

> [!CAUTION]
> **RESEARCH & SCREENING PROTOTYPE ONLY**:
> 1. **Not a Medical Device**: This software is an artificial intelligence screening aid intended to support qualified clinical staff. It has **NOT** received FDA 510(k), CE mark, or CDSCO medical device clearance.
> 2. **Not a Diagnostic Substitute**: The model output does **not** replace a comprehensive binocular indirect ophthalmoscopic (BIO) examination or wide-field digital retinal imaging review performed by a certified pediatric ophthalmologist or trained ROP specialist.
> 3. **Zone & Staging Limitations**: The model classifies overall vascular disease severity (`Normal`, `Pre-Plus`, `Plus`) from posterior pole images. It does not independently localize retinopathy zones (Zone I, II, III) or peripheral stage boundaries (Stages 1-5).
> 4. **Demographic & Equipment Variability**: Model performance may vary depending on camera optics (e.g. RetCam, 3nethra neo, Forus Health), pupil dilation quality, infant ethnicity, and media opacity.

