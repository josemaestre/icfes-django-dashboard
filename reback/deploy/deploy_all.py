"""
Master Deployment Script

Executes the complete deployment process in order:
1. Generate slugs
2. Sync gold tables to prod
3. Verify deployment

Usage:
    python deploy/deploy_all.py
"""
import subprocess
import sys
from pathlib import Path

DEPLOY_DIR = Path(__file__).parent

SCRIPTS = [
    ("01_generate_slugs.py", "Generating slugs"),
    ("02_sync_gold_to_prod.py", "Syncing gold tables to prod"),
    ("03_verify_deployment.py", "Verifying deployment"),
]

def run_script(script_name, description):
    """Run a deployment script and return success status."""
    print("\n" + "=" * 80)
    print(f"RUNNING: {description}")
    print("=" * 80)
    
    script_path = DEPLOY_DIR / script_name
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=False,
            text=True,
            check=True
        )
        
        print(f"\n✅ {description} completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Error running {description}: {e}")
        return False

def main():
    print("=" * 80)
    print("DEPLOYMENT PROCESS - DEV TO PROD")
    print("=" * 80)
    print("\nThis will:")
    print("  1. Generate slugs for all schools")
    print("  2. Sync all gold tables from dev to prod (with backup)")
    print("  3. Verify the deployment")
    
    response = input("\nProceed with deployment? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("\n❌ Deployment cancelled")
        return False
    
    # Run each script in order
    for script_name, description in SCRIPTS:
        success = run_script(script_name, description)
        
        if not success:
            print("\n" + "=" * 80)
            print("❌ DEPLOYMENT FAILED")
            print("=" * 80)
            print(f"\nFailed at: {description}")
            print("Please fix the errors and try again.")
            return False
    
    # All scripts completed successfully
    print("\n" + "=" * 80)
    print("🎉 DEPLOYMENT COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print("\nAll gold tables have been synced from dev to prod.")
    print("The production database is ready to use.")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
