import pygrib
import time
import tqdm
import os

# path to grib data
filepath = "../grib_data"

grib_files = os.listdir(filepath)
grib_files = [os.path.join(filepath, file) for file in grib_files]

start_time = time.time()
gribs = {}
for file in tqdm.tqdm(grib_files):
    grbs = pygrib.open(file)

    if file == grib_files[0]:
        lat, lon = grbs[1].latlons()

    messages = []
    for grb in grbs:
        param_name = grb.parameterName
        data = grb.values

        message = {
            "parameter": param_name,
            "data": data
        }

        messages.append(message)

    gribs[file] = messages

print(f"Time taken: {time.time() - start_time:.2f} seconds")






