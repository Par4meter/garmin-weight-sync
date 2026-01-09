
import argparse
import sys
import logging
import json
import datetime
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from xiaomi.config import ConfigManager
from xiaomi.client import XiaomiClient
from garmin.fit_generator import create_weight_fit_file
from garmin.client import GarminClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def display_weight_data(weights, limit=10):
    """Display weight data in a formatted way"""
    if not weights:
        print("No weight data found.")
        return
    
    print(f"\n{'='*80}")
    print(f"📊 Weight Data Summary - Total Records: {len(weights)}")
    print(f"{'='*80}\n")
    
    # Show latest records
    display_count = min(limit, len(weights))
    print(f"Showing latest {display_count} records:\n")
    
    for i, w in enumerate(weights[:display_count], 1):
        print(f"Record #{i} - {w.get('Date', 'N/A')}")
        print(f"  Weight: {w.get('Weight', 'N/A')} kg")
        print(f"  BMI: {w.get('BMI', 'N/A')}")
        
        if w.get('BodyFat'):
            print(f"  Body Fat: {w.get('BodyFat')}%")
        if w.get('BodyWater'):
            print(f"  Body Water: {w.get('BodyWater')}%")
        if w.get('MuscleMass'):
            print(f"  Muscle Mass: {w.get('MuscleMass')} kg")
        if w.get('BoneMass'):
            print(f"  Bone Mass: {w.get('BoneMass')} kg")
        if w.get('VisceralFat'):
            print(f"  Visceral Fat: {w.get('VisceralFat')}")
        if w.get('BasalMetabolism'):
            print(f"  Basal Metabolism: {w.get('BasalMetabolism')} kcal")
        if w.get('MetabolicAge'):
            print(f"  Metabolic Age: {w.get('MetabolicAge')} years")
        if w.get('BodyScore'):
            print(f"  Body Score: {w.get('BodyScore')}")
        if w.get('HeartRate'):
            print(f"  Heart Rate: {w.get('HeartRate')} bpm")
        
        print()
    
    # Statistics
    if len(weights) > 0:
        weights_values = [w.get('Weight') for w in weights if w.get('Weight')]
        if weights_values:
            print(f"{'='*80}")
            print(f"📈 Statistics")
            print(f"{'='*80}")
            print(f"  Latest Weight: {weights_values[0]} kg")
            print(f"  Average Weight: {sum(weights_values) / len(weights_values):.2f} kg")
            print(f"  Min Weight: {min(weights_values)} kg")
            print(f"  Max Weight: {max(weights_values)} kg")
            print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(description="Xiaomi Weight Sync")
    parser.add_argument("--config", default="users.json", help="Path to users.json config file")
    parser.add_argument("--limit", type=int, default=10, help="Number of records to display")
    parser.add_argument("--fit", action="store_true", help="Generate FIT files for Garmin")
    parser.add_argument("--sync", action="store_true", help="Upload weight data to Garmin Connect")
    parser.add_argument("--output-dir", default="data/garmin-fit", help="Directory for generated FIT files")
    args = parser.parse_args()

    # If --sync is requested, we must also have --fit
    if args.sync:
        args.fit = True

    config_mgr = ConfigManager(args.config)
    users = config_mgr.get_users()

    if not users:
        print(f"No users found in {args.config}. Please add users to the configuration file.")
        
        # Create a template if it doesn't exist/empty
        if not users:
             template = {
                "users": [
                    {
                        "username": "your_xiaomi_username",
                        "password": "your_xiaomi_password",
                        "model": "yunmai.scales.ms103",
                        "token": {
                            "userId": "",
                            "passToken": "",
                            "ssecurity": ""
                        },
                        "garmin": {
                            "email": "your_garmin_email",
                            "password": "your_garmin_password",
                            "domain": "CN"
                        }
                    }
                ]
             }
             with open(args.config, 'w') as f:
                 json.dump(template, f, indent=4)
             print(f"Created template {args.config}")
             return

    for user in users:
        username = user.get("username")
        token = user.get("token")
        model = user.get("model", "yunmai.scales.ms103")
        garmin_config = user.get("garmin")

        if not username:
            continue

        print(f"Processing user: {username}")
        
        client = XiaomiClient(username=username)
        
        if token and token.get("userId") and token.get("passToken"):
            # Set credentials from token
            client.set_credentials(
                user_id=token["userId"],
                ssecurity_encoded=token.get("ssecurity"),
                pass_token=token["passToken"]
            )
            
            try:
                # Validate/Refresh token
                print("Logging in with saved Xiaomi token...")
                new_token_data = client.login_from_token()
                
                # Update token in config if changed
                if new_token_data:
                     config_mgr.update_user_token(username, new_token_data)
                     print("Xiaomi token refreshed and saved")
                
                # Fetch weights
                print(f"Fetching weight data for model: {model}")
                weights = client.get_model_weights(model)
                
                if weights:
                    print(f"Successfully retrieved {len(weights)} weight records")
                    display_weight_data(weights, limit=args.limit)

                    # Save to JSON file
                    output_file = f"data/weight_data_{username}.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(weights, f, indent=2, ensure_ascii=False)
                    print(f"Weight data saved to {output_file}")
                    
                    # Generate FIT file if requested
                    fit_file_path = None
                    if args.fit:
                        fit_output_dir = Path(args.output_dir)
                        fit_output_dir.mkdir(parents=True, exist_ok=True)
                        fit_file_path = fit_output_dir / f"weight_{username}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.fit"
                        create_weight_fit_file(weights, fit_file_path)
                    
                    # Sync to Garmin if requested
                    if args.sync and fit_file_path:
                        if garmin_config and garmin_config.get("email") and garmin_config.get("password"):
                            g_client = GarminClient(
                                email=garmin_config["email"],
                                password=garmin_config["password"],
                                auth_domain=garmin_config.get("domain", "CN")
                            )
                            
                            if g_client.login():
                                print("Synchronizing to Garmin Connect...")
                                status = g_client.upload_fit(fit_file_path)
                                if status == "SUCCESS":
                                    print("✅ Successfully synchronized weight data to Garmin Connect!")
                                elif status == "DUPLICATE":
                                    print("ℹ️ Data already exists on Garmin Connect (Duplicate).")
                                else:
                                    print(f"❌ Garmin sync failed: {status}")
                            else:
                                print("❌ Garmin login failed. Synchronization aborted.")
                        else:
                            print(f"⚠️ Garmin credentials missing for {username}. Skipping sync.")
                else:
                    print("No weight data found")
                
            except Exception as e:
                print(f"Failed to process data for {username}: {e}")
                logger.exception("Detailed error:")
        else:
             print(f"No valid token for {username}. Please run the login tool to generate a token.")
             print("Run: python src/xiaomi/login.py --config users.json")


if __name__ == "__main__":
    main()
