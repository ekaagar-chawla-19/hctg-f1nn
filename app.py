from flask import Flask, jsonify
from flask_cors import CORS
import requests, json

app = Flask(__name__)
CORS(app)

OPENF1 = "https://api.openf1.org/v1"
ERGAST = "https://api.jolpi.ca/ergast/f1"

CURRENT_YEAR = 2026

def openf1(endpoint, params=None):
    r = requests.get(f"{OPENF1}/{endpoint}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def ergast(path):
    r = requests.get(f"{ERGAST}/{path}.json?limit=100", timeout=10)
    r.raise_for_status()
    return r.json()


@app.route("/api/drivers")
def get_drivers():
    try:
        sessions = openf1("sessions", {"year": CURRENT_YEAR, "session_type": "Race"})
        if not sessions:
            return jsonify({"error": "No sessions found"}), 404

        latest_session = sessions[-1]["session_key"]
        drivers = openf1("drivers", {"session_key": latest_session})

        result = []
        for d in drivers:
            result.append({
                "number":       d.get("driver_number"),
                "code":         d.get("name_acronym"),
                "name":         d.get("full_name"),
                "team":         d.get("team_name"),
                "team_color":   "#" + d.get("team_colour", "888888"),
                "country_code": d.get("country_code"),
                "headshot_url": d.get("headshot_url"),
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/standings/drivers")
def get_driver_standings():
    try:
        data = ergast(f"{CURRENT_YEAR}/driverStandings")
        standings_list = (
            data["MRData"]["StandingsTable"]
               ["StandingsLists"][0]["DriverStandings"]
        )

        result = []
        for s in standings_list:
            d = s["Driver"]
            c = s["Constructors"][0] 
            result.append({
                "position": int(s["position"]),
                "points":   float(s["points"]),
                "wins":     int(s["wins"]),
                "driver": {
                    "code":        d.get("code", ""),
                    "name":        f"{d['givenName']} {d['familyName']}",
                    "nationality": d.get("nationality", ""),
                },
                "constructor": {
                    "name": c["name"],
                }
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/standings/constructors")
def get_constructor_standings():
    try:
        data = ergast(f"{CURRENT_YEAR}/constructorStandings")
        standings_list = (
            data["MRData"]["StandingsTable"]
               ["StandingsLists"][0]["ConstructorStandings"]
        )

        result = []
        for s in standings_list:
            c = s["Constructor"]
            result.append({
                "position": int(s["position"]),
                "points":   float(s["points"]),
                "wins":     int(s["wins"]),
                "constructor": {
                    "name":        c["name"],
                    "nationality": c.get("nationality", ""),
                }
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/schedule")
def get_schedule():
    try:
        data = ergast(f"{CURRENT_YEAR}")
        races = data["MRData"]["RaceTable"]["Races"]

        result = []
        for r in races:
            result.append({
                "round":    int(r["round"]),
                "name":     r["raceName"],
                "country":  r["Circuit"]["Location"]["country"],
                "locality": r["Circuit"]["Location"]["locality"],
                "circuit":  r["Circuit"]["circuitName"],
                "date":     r["date"],
                "time":     r.get("time", ""),
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/qualifying/<int:round_number>")
def get_qualifying(round_number):
    try:
        data = ergast(f"{CURRENT_YEAR}/{round_number}/qualifying")
        quali = data["MRData"]["RaceTable"]["Races"]

        if not quali:
            return jsonify({"error": "No qualifying data found for this round"}), 404

        race = quali[0]
        result = []

        for q in race["QualifyingResults"]:
            d = q["Driver"]
            c = q["Constructor"]
            result.append({
                "position": int(q["position"]),
                "driver": {
                    "code": d.get("code", ""),
                    "name": f"{d['givenName']} {d['familyName']}",
                },
                "constructor": c["name"],
                "q1": q.get("Q1", "—"),
                "q2": q.get("Q2", "—"),
                "q3": q.get("Q3", "—"),
            })

        return jsonify({
            "race_name": race["raceName"],
            "results":   result,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/results/latest")
def get_latest_results():
    try:
        data = ergast(f"{CURRENT_YEAR}/last/results")
        races = data["MRData"]["RaceTable"]["Races"]  

        if not races:
            return jsonify({"error": "No results yet"}), 404

        race = races[0]
        result = []

        for r in race["Results"]: 
            d = r["Driver"]
            c = r["Constructor"]
            result.append({
                "position":    int(r["position"]),
                "driver": {
                    "code": d.get("code", ""),
                    "name": f"{d['givenName']} {d['familyName']}",
                },
                "constructor": c["name"],      
                "grid":        int(r.get("grid", 0)),
                "laps":        int(r.get("laps", 0)),
                "status":      r.get("status", ""),
                "points":      float(r.get("points", 0)), 
                "fastest_lap": r.get("FastestLap", {}).get("Time", {}).get("time", ""),
            })
        return jsonify({
            "race_name": race["raceName"],
            "round":     int(race["round"]),
            "date":      race["date"],
            "results":   result,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/telemetry/<int:session_key>/<int:driver_number>")
def get_telemetry(session_key, driver_number):
    try:
        car_data = openf1("car_data", {
            "session_key":   session_key,
            "driver_number": driver_number,
        })

        samples = car_data[-200:] if len(car_data) > 200 else car_data

        result = [{
            "date":     s.get("date"),
            "speed":    s.get("speed"),
            "throttle": s.get("throttle"),
            "brake":    s.get("brake"),
            "rpm":      s.get("rpm"),
            "gear":     s.get("n_gear"),
            "drs":      s.get("drs"),
        } for s in samples]

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/latest")
def get_latest_session():
    try:
        sessions = openf1("sessions", {"year": CURRENT_YEAR})
        if not sessions:
            return jsonify({"error": "No sessions found"}), 404

        latest = sessions[-1]
        return jsonify({
            "session_key":  latest["session_key"],   
            "session_name": latest["session_name"],  
            "session_type": latest["session_type"],
            "date_start":   latest["date_start"],
            "circuit_name": latest["circuit_short_name"],
            "country":      latest["country_name"],
            "year":         latest["year"],
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n🏎  F1 Oracle backend running at http://localhost:5000\n")  
    app.run(debug=True, port=5000)