import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from matplotlib.collections import LineCollection
from timple.timedelta import strftimedelta

import fastf1
from fastf1 import plotting
from fastf1.core import Laps

print("Welcome to the Formula One Race & Qualifying Plotter")

# === User Inputs ===
year = int(input("Year: "))
race_name = input("Race: ")

# Setup plotting
plotting.setup_mpl(mpl_timedelta_support=True, misc_mpl_mods=False, color_scheme='fastf1')

# Load sessions
race = fastf1.get_session(year, race_name, 'R')
race.load()

qualy = fastf1.get_session(year, race_name, 'Q')
qualy.load()

# === Race: Top 10 finishers ===
results = race.results.sort_values('Position')
top_10 = results.head(10)
top_10_drivers = top_10['Abbreviation'].tolist()

# === Qualifying: Fastest laps ===
drivers_qualy = pd.unique(qualy.laps['Driver'])
list_fastest_laps = []
for drv in drivers_qualy:
    fastest_lap = qualy.laps.pick_drivers(drv).pick_fastest()
    if not fastest_lap.empty:
        list_fastest_laps.append(fastest_lap)

fastest_laps = Laps(list_fastest_laps).sort_values(by='LapTime').reset_index(drop=True)
if fastest_laps.empty:
    print("No qualifying laps found!")
    exit()

pole_lap = fastest_laps.pick_fastest()
fastest_laps['LapTimeDelta'] = fastest_laps['LapTime'] - pole_lap['LapTime']
top_15_qualy = fastest_laps.head(15)

# === Get telemetry of fastest driver for track map ===
telemetry_available = True
try:
    fastest_driver = race.laps.pick_fastest()['Driver']
    fastest_lap = race.laps.pick_drivers(fastest_driver).pick_fastest()
    telemetry = fastest_lap.get_telemetry()
    x = telemetry['X']
    y = telemetry['Y']
    speed = telemetry['Speed']

    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)

except Exception as e:
    telemetry_available = False
    print(f"⚠️ Could not load telemetry: {e}")

# === Create figure with 5 subplots ===
fig, axs = plt.subplots(1, 5, figsize=(26, 6),
                        gridspec_kw={'width_ratios': [3, 3, 0.5, 1.5, 1.8]})

# --- Plot 1: Race lap times ---
ax1 = axs[0]
for driver in top_10_drivers:
    laps = race.laps.pick_drivers(driver).pick_quicklaps().reset_index()
    if laps.empty:
        continue
    style = plotting.get_driver_style(identifier=driver, style=['color', 'linestyle'], session=race)
    ax1.plot(laps['LapNumber'], laps['LapTime'], **style, label=driver)

ax1.set_title(f"Top 10 Lap Times\n{race.event['EventName']} {year}", fontsize=11)
ax1.set_xlabel("Lap Number")
ax1.set_ylabel("Lap Time")
ax1.legend(title="Driver", fontsize=8)
ax1.grid(True)

# --- Plot 2: Race position per lap ---
ax2 = axs[1]
for driver in top_10_drivers:
    driver_laps = race.laps.pick_drivers(driver).reset_index()
    # Filter laps with valid Position (avoid NaNs)
    driver_laps = driver_laps[driver_laps['Position'].notna()]
    if driver_laps.empty:
        continue
    # Sort by lap number to keep order
    driver_laps = driver_laps.sort_values('LapNumber')
    style = plotting.get_driver_style(identifier=driver, style=['color'], session=race)
    ax2.plot(driver_laps['LapNumber'], driver_laps['Position'], label=driver, color=style['color'])

ax2.set_title("Race Position Per Lap (Top 10)", fontsize=11)
ax2.set_xlabel("Lap Number")
ax2.set_ylabel("Position")
ax2.invert_yaxis()  # Position 1 at top
ax2.grid(True)
ax2.legend(fontsize=7)

# --- Plot 3: Final race time bar chart ---
final_times = []
for driver in top_10_drivers:
    laps = race.laps.pick_drivers(driver)
    total_time = laps['LapTime'].sum()
    final_times.append(total_time.total_seconds())

ax3 = axs[2]
bars = ax3.barh(
    top_10_drivers,
    final_times,
    color=[plotting.get_driver_color(d, session=race) for d in top_10_drivers]
)
ax3.set_xlabel("Race Time (s)")
ax3.set_title("Final Race Times", fontsize=11)
ax3.invert_yaxis()

for bar, time in zip(bars, final_times):
    ax3.text(
        time - (0.05 * max(final_times)),  # inside bar near right edge
        bar.get_y() + bar.get_height() / 2,
        f"{time:.1f}s",
        va='center',
        ha='right',
        fontsize=7,
        color='white',
        fontweight='bold'
    )

# --- Plot 4: Qualifying delta bar chart ---
team_colors = []
for _, lap in top_15_qualy.iterlaps():
    color = plotting.get_team_color(lap['Team'], session=qualy)
    team_colors.append(color)

ax4 = axs[3]
ax4.barh(top_15_qualy['Driver'], top_15_qualy['LapTimeDelta'].dt.total_seconds(),
         color=team_colors, edgecolor='grey')
ax4.set_xlabel("Delta to Pole (s)")
ax4.set_title("Top 15 Qualifying", fontsize=11)
ax4.invert_yaxis()
ax4.grid(True, axis='x', linestyle='--')

# --- Plot 5: Telemetry track map ---
ax5 = axs[4]
if telemetry_available:
    ax5.axis('off')
    ax5.set_title(f"{fastest_driver} Fastest Lap\nSpeed Map", fontsize=11)

    ax5.plot(x, y, color='black', linestyle='-', linewidth=16, zorder=0)

    norm = plt.Normalize(speed.min(), speed.max())
    lc = LineCollection(segments, cmap=mpl.cm.plasma, norm=norm, linewidth=4)
    lc.set_array(speed)
    ax5.add_collection(lc)

    # Add inline colorbar
    cbaxes = fig.add_axes([0.87, 0.12, 0.10, 0.02])  # Adjust position for 5 plots
    colorbar = mpl.colorbar.ColorbarBase(cbaxes, cmap=mpl.cm.plasma,
                                         norm=norm, orientation='horizontal')
    colorbar.set_label("Speed (km/h)", fontsize=9)

else:
    ax5.text(0.5, 0.5, "Telemetry Not Available", ha='center', va='center', fontsize=10)
    ax5.axis('off')

# === Main title and layout ===
pole_lap_str = strftimedelta(pole_lap['LapTime'], '%m:%s.%ms')
fig.suptitle(f"{race.event['EventName']} {year} Race & Qualifying Overview\n"
             f"Pole Lap: {pole_lap_str} ({pole_lap['Driver']})",
             fontsize=14, y=0.98)

# Adjust spacing between plots
plt.subplots_adjust(wspace=0.6, top=0.92)
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.show()
