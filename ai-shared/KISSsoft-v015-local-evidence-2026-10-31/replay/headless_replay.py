from pathlib import Path
import argparse,json
import win32com.client
ap=argparse.ArgumentParser();ap.add_argument('native',type=Path);ap.add_argument('module',choices=['Z012','W010','W050','M02A','M010']);a=ap.parse_args()
k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule(a.module,False);k.SetSilentMode(True)
try:
 k.LoadFile(str(a.native.resolve()));ok=bool(k.CalculateRetVal())
 print(json.dumps({'module':a.module,'version':k.GetKsoftVersion(),'calculate_ok':ok,'messages':k.Message()},ensure_ascii=False,indent=2))
 if not ok:raise SystemExit(1)
finally:k.ReleaseModule()
