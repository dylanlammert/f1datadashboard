# needed view models import
# from ViewModels.raceSimulationVM import PlayControlsVM
# from ViewModels.trackStatusVM import TrackStatusVM

# import things needed for graphs
import matplotlib.pyplot as plt
import numpy as np
#from UI.Theme import theme
import fastf1
import pandas as pd
from UI.Theme import theme
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

""" 
    TODO:
        - make the canvas draw based on current theme
        - make the draw go based off of db
        - allow this to run offline
        - if offline only refer to the db for data
"""

class SimulationCanvas(FigureCanvasQTAgg):
    def __init__(self):
        self.figure = Figure(facecolor = theme.background)
        self.ax = self.figure.add_axes([0,0,1,1])
        self.drivers: list
        super().__init__(self.figure)
        self.ax.set_axis_off()
        self.ax.set_aspect("equal", adjustable="datalim")
        self.ax.set_facecolor("none")
        self.driverGPSPos: dict[str , pd.DataFrame] = {}
        #self.drawTrackOutline()
        """
        for spine in self.ax.spines.values():
            spine.set_visible(False)
        """
        self.ax.margins(0.03)
        self.loadDriverGPSPos()
        #print(f" VER gps pos data frame \n {self.getDriverGPSPos(abbr = "VER")}")

    def getDriverGPSPos(self, abbr: str) -> pd.DataFrame | None:
        return self.driverGPSPos.get(abbr.upper()).head(5)

    def loadDriverGPSPos(self, year: int = 2023, event: str = "Bahrain", sessionType: str = "R"):
        session = fastf1.get_session(year, event, sessionType)
        session.load(telemetry=True, laps=True, weather=False, messages=False)

        for driverNumber in session.drivers:
            abbr = session.get_driver(driverNumber)["Abbreviation"]
            laps = session.laps.pick_drivers(driverNumber)

            frames = []
            for _, lap in laps.iterlaps():
                pos = lap.get_pos_data().assign(LapNumber=lap["LapNumber"])
                frames.append(pos)

            if frames:
                # one DataFrame per driver: X, Y, Z, Status, Time, SessionTime, LapNumber, ...
                self.driverGPSPos[abbr] = pd.concat(frames, ignore_index=True)

        
    def drawTrackOutline(self):
        # make this modular and don't load a fastf1 session every time pull data from rows in the database
        session = fastf1.get_session(2023, 'Bahrain', 'R')
        session.load()

        lap = session.laps.pick_fastest()
        pos = lap.get_pos_data()
        #print(pos.columns)
        circuit_info = session.get_circuit_info()
        # Get an array of shape [n, 2] where n is the number of points and the second
        # axis is x and y.
        track = pos.loc[:, ('X', 'Y')].to_numpy()

        # Convert the rotation angle from degrees to radian.
        track_angle = circuit_info.rotation / 180 * np.pi

        # Rotate and plot the track map.
        rotated_track = self.rotate(track, angle=track_angle)
        self.ax.plot(rotated_track[:, 0], rotated_track[:, 1])
        offset_vector = [500, 0]  # offset length is chosen arbitrarily to 'look good'

# Iterate over all corners.
        for _, corner in circuit_info.corners.iterrows():
            # Create a string from corner number and letter
            txt = f"{corner['Number']}{corner['Letter']}"

            # Convert the angle from degrees to radian.
            offset_angle = corner['Angle'] / 180 * np.pi

            # Rotate the offset vector so that it points sideways from the track.
            offset_x, offset_y = self.rotate(offset_vector, angle=offset_angle)

            # Add the offset to the position of the corner
            text_x = corner['X'] + offset_x
            text_y = corner['Y'] + offset_y

            # Rotate the text position equivalently to the rest of the track map
            text_x, text_y = self.rotate([text_x, text_y], angle=track_angle)

            # Rotate the center of the corner equivalently to the rest of the track map
            track_x, track_y = self.rotate([corner['X'], corner['Y']], angle=track_angle)

            # Draw a circle next to the track.
            self.ax.scatter(text_x, text_y, color='grey', s=140)

            # Draw a line from the track to this circle.
            self.ax.plot([track_x, text_x], [track_y, text_y], color='grey')

            # Finally, print the corner number inside the circle.
            self.ax.text(text_x, text_y, txt,
                    va='center_baseline', ha='center', size='small', color='white')
        
        # run outside of the loop
        #plt.title(session.event['Location'])
        # plt.show()
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw_idle()

    def rotate(self, xy, *, angle):
        rot_mat = np.array([[np.cos(angle), np.sin(angle)],
                            [-np.sin(angle), np.cos(angle)]])
        return np.matmul(xy, rot_mat)

if __name__ == "__main__":
    simulation = SimulationCanvas()
