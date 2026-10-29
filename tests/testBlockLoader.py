import unittest
from Services.dbhandler import DBhandler

greenColor = "\033[92m"
resetColor = "\033[0m"
redColor = "\033[91m"


class BlockLoaderTester(unittest.TestCase):

    # example print of loading data block out of db just going for session 1
    def test_view_print_data_blocks(self):
        dbHandler = DBhandler()
        lapDataBlock = dbHandler.getLapsDataBlock(
            attributeList= ["driver", "team", "lap_number", "compound", "tyre_life", "position", "lap_start_time", "lap_end_time"],
            sessionID= 1)
        telemetryDataBlock = dbHandler.getTelemetryDataBlock(
            attributeList= ["driver_code","session_time", "x_pos", "y_pos", "distance_to_driver_ahead", "gear", "throttle", "brake", "drs", "speed", "rpm"],
            sessionID = 1
        )
        print(f"{redColor}viewing lapDataBlock{resetColor}")
        for dataItem in lapDataBlock:
            print(dataItem)

        print(f"{redColor}viewing telemetryDataBlock{resetColor}")
        for dataItem in telemetryDataBlock:
            print(dataItem)

if __name__ == "__main__":
    unittest.main()