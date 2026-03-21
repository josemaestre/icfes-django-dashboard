"""
Master Deployment Script

Executes the complete deployment process in order:
1. Run ML scripts (enrich gold tables in dev.duckdb)
2. Generate slugs
3. Sync gold tables to prod
4. Verify deployment
5. Notify IndexNow

Prerequisite (run separately before this script):
    dbt run --full-refresh -s colegios_ano+

Usage:
    python deploy/deploy_all.py
"""
import subprocess
import sys
from pathlib import Path

DEPLOY_DIR  = Path(__file__).parent
DS_DIR      = Path.home() / "data_science"   # /home/ubuntu/data_science on EC2

# ML scripts — run in order (some have dependencies)
ML_SCRIPTS = [
    "train_potencial_model.py",
    "train_potencial_ingles.py",
    "train_prioridad_ingles.py",           # depende de train_potencial_ingles
    "train_predictor_ingles.py",
    "train_school_clusters.py",
    "train_clusters_depto_ingles.py",
    "train_clusters_transformadores_ingles.py",
    "train_social_predictor.py",
    "train_social_clusters.py",
    "build_ml_palancas.py",
    "build_social_estrato.py",
    # Análisis motivacional
    "train_perfil_motivacional.py",
    "train_momentum_motivacional.py",
    "train_polarizacion_academica.py",
]

# Deploy scripts — run after ML
DEPLOY_SCRIPTS = [
    ("01_generate_slugs.py",   "Generating slugs"),
    ("02_sync_gold_to_prod.py","Syncing gold tables to prod"),
    ("03_verify_deployment.py","Verifying deployment"),
    ("04_notify_indexnow.py",  "Notifying IndexNow of updated URLs"),
]


def run_script(script_path, description):
    print("\n" + "=" * 80)
    print(f"RUNNING: {description}")
    print("=" * 80)
    try:
        subprocess.run([sys.executable, str(script_path)],
                       capture_output=False, text=True, check=True)
        print(f"\n✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Error running {description}: {e}")
        return False


def run_ml_scripts():
    print("\n" + "=" * 80)
    print("PHASE 1 — ML SCRIPTS (enriching gold tables)")
    print("=" * 80)
    for script_name in ML_SCRIPTS:
        script_path = DS_DIR / script_name
        if not script_path.exists():
            print(f"\n  [SKIP] {script_name} (not found in {DS_DIR})")
            continue
        success = run_script(script_path, script_name)
        if not success:
            return False
    return True


def main():
    print("=" * 80)
    print("DEPLOYMENT PROCESS - DEV TO PROD")
    print("=" * 80)
    print("\nThis will:")
    print("  Phase 1 — Run all ML scripts (writes to dev.duckdb gold)")
    print("  Phase 2 — Generate slugs")
    print("  Phase 3 — Sync all gold tables from dev to prod (with backup)")
    print("  Phase 4 — Verify the deployment")
    print("  Phase 5 — Notify IndexNow of updated URLs (Bing, Yandex)")
    print("\nPrerequisite: dbt run --full-refresh -s colegios_ano+ must have run first.")

    response = input("\nProceed with deployment? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("\n❌ Deployment cancelled")
        return False

    # Phase 1: ML scripts
    if not run_ml_scripts():
        print("\n❌ DEPLOYMENT FAILED at ML phase")
        return False

    # Phase 2-5: Deploy scripts
    print("\n" + "=" * 80)
    print("PHASE 2 — DEPLOY SCRIPTS")
    print("=" * 80)
    for script_name, description in DEPLOY_SCRIPTS:
        success = run_script(DEPLOY_DIR / script_name, description)
        if not success:
            print(f"\n❌ DEPLOYMENT FAILED at: {description}")
            return False

    print("\n" + "=" * 80)
    print("🎉 DEPLOYMENT COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print("\nAll gold tables (dbt + ML) have been synced from dev to prod.")
    print("The production database is ready to use.")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
