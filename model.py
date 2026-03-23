''' This is going to be the actual ML model...'''
import os
import json
import argparse
import requests
import numpy as np
import panda as pd
from datetime import datetime
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, accuracy_score
import joblib


ERGAST = "https://api.jolpi.ca/ergast/f1"
START_YEAR = 2010
END_YEAR = 2026
MODEL_PATH = "f1_model.pt"
SCALER_PATH = "f1_scaler.pkl"
DATA_CACHE = "f1_data_cache.csv"

FEATURES = [ 
    "grid_position",
    "driver_avg_pos_5",
    "driver_win_rate",
    "driver_dnf_rate",
    "constructor_avg_position",
    "constructor_points",
    "track_driver_avg",
    "track_constructor_avg",
    "season_round",
    "season_progrss",
    "chapionship_pos",
    "gap_to_leader",
] 

def ergast_get(path,limit=100):
    url = f"{ERGAST}/{path}.json?limit={limit}"
    r = requests.get(url, timeout=15)
    r.raise_for_status
    return r.json()

def fetch_season_results(year):
    print(f"Fetching {year} results......")
    try:
        data = ergast_get(f"{year}/results", limit = 1000)
        races = data["MRData"]["RaceTable"]["Races"] #forming a dictionary structure
        if not races:
            print(f"No races found for {year}, skipping forward")
            return []
        rows = []
        for race in races:
            result = race.get("Results",[])
            if not result:
                continue
            for r in result:
                d = r["Driver"]
                c = r["Constructor"]

                rows.append = ({
                    "year": year,
                    "round": int(race["round"]),
                    "total_rounds": None,
                    "race_name": race["raceName"],
                    "circuit_id": race["Circuit"]["circuitId"],
                    "driver_id": d["driverId"],
                    "constructor_id": c["constructorId"],
                    "grid": int(r.get("grid",0)),
                    "position": int(r["position"]) if str(r.get("position",0)).isDigit() else 99,
                    "points": float(r.get("points", 0)),
                    "status": r.get("status", ""),
                    "laps": int(r.get("laps",0)),
                })
                completed = len(set(r["round"] for r in rows))
                print(f"{year}: {completed} completed races, {len(rows)} driver enties")
                return rows
    except Exception as e:
        print(f" couldnt fetch {year}: {e}")
        return []
    
def fetch_all_data(force_refresh=False):
    if (os.path.exists(DATA_CACHE) and not force_refresh):
        print(f"loading cached data from {DATA_CACHE}")
        return pd.read_csv(DATA_CACHE)
    print(f"fetching data {START_YEAR} to {END_YEAR}")
    all_rows = []
    for year in range(START_YEAR, END_YEAR + 1):
        rows = fetch_season_results(year)
        all_rows.extend(rows)
    if(not all_rows):
        raise RuntimeError("no data fetched")
    df = pd.DataFrame(all_rows)

    total_rounds = df.groupby("year")["round"].max().rename("total_rounds")
    df = df.drop(columns=["total_rounds"], errors = "ignore")
    df = df.join(total_rounds,on="year")
    df.to_csv(DATA_CACHE, index = False)
    return df

def engineer_features(df):
    '''need to return a feature matrix X with columns matching features plus target 
    columns y_pos & y_podium '''

    df = df.copy().sort_values(["year","round"]).reset_index(drop=True)

    df["dnf"] = df["status"].apply(
        lambda s: 0 if s in ("Finished", "+1 Lap", "+2 Laps", "+3 Laps") else 1
    )
    rows = []

    for _, race_group in df.groupby(["year","round"]):
        year = race_group["year"].iloc[0]
        rnd = race_group["round"].iloc[0]
        total = race_group["total_rounds"].iloc[0]

        history = df[(df["year"] <= year) & ~((df["year"] == year) & (df["round"] >= rnd))]

        for _, entry in race_group.iterrows():
            drv = entry["driver_id"]
            con = entry["constructor_id"]
            cirt = entry["circuit_id"]

            drv_hist = history[history["driver_id"] == drv].tail(5)
            




