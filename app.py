from io import BytesIO
import base64
from flask import Flask, render_template_string, request
import pandas as pd
import matplotlib.pyplot as plt
from timple.timedelta import strftimedelta
import fastf1
from fastf1 import plotting
from fastf1.core import Laps

app = Flask(__name__)

HTML_PAGE = """
<!doctype html>
<title>F1 Race & Qualifying Plotter</title>
<h1>F1 Race & Qualifying Plotter</h1>
<form method="post">
  Year: <input name="year" type="number" required value="{{ year }}"><br><br>
  Race (e.g. 'Monaco'): <input name="race" type="text" required value="{{ race }}"><br><br>
  <input type="submit" value="Plot">
</form>
{% if plot_url %}
  <h2>Plots for {{ year }} {{ race }} Race</h2>
  <img src="data:image/png;base64,{{ plot_url }}" alt="F1 Plot">
{% endif %}
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    plot_url = None
    year = ''
    race_name = ''
    if request.method == 'POST':
        try:
            year = int(request.form['year'])
            race_name = request.form['race']

            # Setup plotting style
            plotting.setup_mpl(mpl_timedelta_support=True, misc_mpl_mods=False, color_scheme='fastf1')

            # Load sessions
            race = fastf1.get_session(year, race_name, 'R')
            race.load()

            qualy = fastf1.get_session(year, race_name, 'Q')
            qualy.load()

            # Race top 10 finishers
            results = race.results.sort_values('Position')
            top_10 = results.head(10)
            top_10_drivers = top_10['Abbreviation'].tolist()

            # Qualifying fastest laps
            drivers_qualy = pd.unique(qualy.laps['Driver'])
            list_fastest_laps = []
            for drv in drivers_qualy:
                fastest_lap = qualy.laps.pick_drivers(drv).pick_fastest()
                if not fastest_lap.empty:
                    list_fastest_laps.append(fastest_lap)
            fastest_laps = Laps(list_fastest_laps).sort_values(by='LapTime').reset_index(drop=True)

            if len(fastest_laps) == 0:
                return render_template_string(HTML_PAGE, year=year, race=race_name,
                                              plot_url=None,
                                              error="No qualifying laps found!")

            pole_lap = fastest_laps.pick_fastest()
            fastest_laps['LapTimeDelta'] = fastest_laps['LapTime'] - pole_lap['LapTime']

            top_15_qualy = fastest_laps.head(15)

            # Create figure
            fig, axs = plt.subplots(1, 3, figsize=(18, 6),
                                    gridspec_kw={'width_ratios': [3, 0.5, 1.2]})

            # Plot 1: Race lap times
            ax1 = axs[0]
            for driver in top_10_drivers:
                laps = race.laps.pick_drivers(driver).pick_quicklaps().reset_index()
                if laps.empty:
                    continue
                style = plotting.get_driver_style(identifier=driver, style=['color', 'linestyle'], session=race)
                ax1.plot(laps['LapNumber'], laps['LapTime'], **style, label=driver)
            ax1.set_title(f"Top 10 Finishers - Lap Times\n{race.event['EventName']} {year}", fontsize=12)
            ax1.set_xlabel("Lap Number")
            ax1.set_ylabel("Lap Time")
            ax1.legend(title="Driver")
            ax1.grid(True)

            # Plot 2: Final race times
            final_times = []
            for driver in top_10_drivers:
                laps = race.laps.pick_drivers(driver)
                total_time = laps['LapTime'].sum()
                final_times.append(total_time.total_seconds())
            ax2 = axs[1]
            bars = ax2.barh(
                top_10_drivers,
                final_times,
                color=[plotting.get_driver_color(d, session=race) for d in top_10_drivers]
            )
            ax2.set_xlabel("Total Race Time (s)")
            ax2.set_title("Final Race Time\nTop 10 Drivers", fontsize=12)
            ax2.invert_yaxis()
            for bar, time in zip(bars, final_times):
                ax2.text(time + 1, bar.get_y() + bar.get_height() / 2, f"{time:.1f}s", va='center')

            # Plot 3: Qualifying delta
            team_colors = []
            for _, lap in top_15_qualy.iterlaps():
                color = plotting.get_team_color(lap['Team'], session=qualy)
                team_colors.append(color)
            ax3 = axs[2]
            ax3.barh(top_15_qualy['Driver'], top_15_qualy['LapTimeDelta'].dt.total_seconds(),
                     color=team_colors, edgecolor='grey')
            ax3.set_xlabel("Qualifying Lap Time Delta (s)")
            ax3.set_title("Qualifying Lap Time\nDelta to Pole", fontsize=12)
            ax3.invert_yaxis()
            ax3.grid(True, axis='x', linestyle='--')

            plt.subplots_adjust(wspace=0.5, top=0.85)
            pole_lap_str = strftimedelta(pole_lap['LapTime'], '%m:%s.%ms')
            fig.suptitle(f"{race.event['EventName']} {year} Race & Qualifying Analysis\n"
                         f"Pole Lap: {pole_lap_str} ({pole_lap['Driver']})", fontsize=14)

            plt.tight_layout(rect=[0, 0, 1, 0.85])

            # Save plot to PNG in memory
            buf = BytesIO()
            plt.savefig(buf, format="png", bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            plot_data = base64.b64encode(buf.read()).decode('ascii')

            plot_url = plot_data

        except Exception as e:
            return render_template_string(HTML_PAGE, year=year, race=race_name, plot_url=None,
                                          error=f"Error: {str(e)}")

    return render_template_string(HTML_PAGE, year=year, race=race_name, plot_url=plot_url)

if __name__ == "__main__":
    app.run(debug=True)
