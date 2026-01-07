import csv
import time
import os
import tqdm
import math
import json
from typing import List

import numpy as np

import eccodes
import concurrent.futures
from bitgroup import BitGroupReader

# compile the c modules using the setup.py file
os.system("python3 setup.py build_ext --inplace")
import bitreader_c
import utils 
    

def parse_single_message(gid: int, message_number: int, lat_grid: np.ndarray, lon_grid: np.ndarray) -> dict:
    """
    Parse a single GRIB message.
    """
    def get_optional_key(gid, key):
        """Helper function to safely get a key if it exists."""
        try:
            return eccodes.codes_get(gid, key)
        except (eccodes.KeyValueNotFoundError):
            return None

    # Collect all needed keys at once if possible (you can customize based on available methods)
    keys_to_fetch = [
        'name', 'offsetSection7', 'binaryScaleFactor', 'decimalScaleFactor', 'referenceValue',
        'bitsPerValue', 'typeOfOriginalFieldValues', 'numberOfDataPoints', 'groupSplittingMethodUsed',
        'numberOfGroupsOfDataValues', 'referenceForGroupWidths', 'numberOfBitsUsedForTheGroupWidths',
        'referenceForGroupLengths', 'lengthIncrementForTheGroupLengths', 'trueLengthOfLastGroup',
        'numberOfBitsForScaledGroupLengths', 'orderOfSpatialDifferencing', 'numberOfOctetsExtraDescriptors',
        'missingValueManagementUsed', 'section7Length','dataTime', 'dataDate', 'level', 'levelType'
    ]

    data = {key: get_optional_key(gid, key) for key in keys_to_fetch}

    raw_message = eccodes.codes_get_message(gid)
    raw_data = raw_message[data['offsetSection7']:]

    # unscale the reference value by the decimal scale factor
    reference_value = data['referenceValue'] * math.pow(10, -data['decimalScaleFactor'])

    eccodes.codes_release(gid)
    return {
        "parameter_name": data['name'],
        "message_number": message_number + 1,
        "binary_scale_factor": data['binaryScaleFactor'],
        "decimal_scale_factor": data['decimalScaleFactor'],
        "reference_value": reference_value,
        "bitpervalue": data['bitsPerValue'],
        "type_of_original_field_values": data['typeOfOriginalFieldValues'],
        "total_data_points": data['numberOfDataPoints'],
        "group_splitting_method": data['groupSplittingMethodUsed'],
        "number_of_groups_of_data_values": data['numberOfGroupsOfDataValues'],
        "reference_for_group_widths": data['referenceForGroupWidths'],
        "number_of_bits_for_group_widths": data['numberOfBitsUsedForTheGroupWidths'],
        "reference_for_group_lengths": data['referenceForGroupLengths'],
        "length_increment_for_the_group_lengths": data['lengthIncrementForTheGroupLengths'],
        "true_length_of_last_group": data['trueLengthOfLastGroup'],
        "number_of_bits_for_scaled_group_lengths": data['numberOfBitsForScaledGroupLengths'],
        "order_of_spatial_differencing": data['orderOfSpatialDifferencing'],
        "number_of_octets_extra_descriptors": data['numberOfOctetsExtraDescriptors'],
        "missing_value_management": data['missingValueManagementUsed'],
        "section7_length": data['section7Length'],
        "latitudes": lat_grid,
        "longitudes": lon_grid,
        "raw_data": raw_data
    }

def parse_grib_file(filename: str, lat_grid: np.ndarray, lon_grid: np.ndarray) -> list:
    """
    Parse a GRIB file.
    """
    messages = []
    message_index = 0
    
    with open(filename, 'rb') as f:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_gid = {}
            
            msg_count = 0
            message_idxs = [8, 59, 60, 61, 63, 70, 74, 83, 122]
            while True:
                gid = eccodes.codes_grib_new_from_file(f)
                if gid is None:
                    break

                # Capture the current message index for this thread
                current_index = message_index
                if msg_count >= len(message_idxs):
                    break
                if message_idxs[msg_count] == current_index:
                    # Pass the current index to the thread
                    future = executor.submit(parse_single_message, gid, current_index, lat_grid, lon_grid)
                    future_to_gid[future] = gid
                    msg_count += 1
                

                message_index += 1  # Increment the message index after submission
            
            for future in concurrent.futures.as_completed(future_to_gid):
                try:
                    messages.append(future.result())
                except Exception as e:
                    print(f"Error processing message: {e}")

    # sort messages by message number
    messages.sort(key=lambda x: x["message_number"])

    return messages


def extract_initial_values(message: dict, bit_reader: bitreader_c.BitReader) -> tuple:
    order_of_spatial_differencing = message['order_of_spatial_differencing']
    extra_descriptors_octets = message['number_of_octets_extra_descriptors']

    # Number of bytes per undifferenced value (determined by extra descriptor octets)
    value_size = extra_descriptors_octets * 8  # Convert to bits

    if order_of_spatial_differencing == 1:
        # First-order differencing (one undifferenced value and one minimum)
        g1 = bit_reader.read_uint(value_size)
        g_min = bit_reader.read_uint(value_size)
        return (g1, g_min)

    elif order_of_spatial_differencing == 2:
        # Second-order differencing (two undifferenced values and one minimum)
        h1 = bit_reader.read_int(value_size)
        h2 = bit_reader.read_int(value_size)
        h_min = bit_reader.read_int(value_size)
        return (h1, h2, h_min)
    

def extract_packed_values(bit_reader: bitreader_c.BitReader, bit_groups: list) -> np.ndarray:
    """
    Extract the packed values from the bit groups.
    """
    packed_values = []
    for group in bit_groups:
        packed_values.extend(group.read_data(bit_reader))
    return np.array(packed_values, dtype=np.float64)




# load lat/lon grids into cache
def load_lat_lon_grid(filename: str) -> tuple:
    with open(filename, 'rb') as f:
        gid = eccodes.codes_grib_new_from_file(f)

    ni = eccodes.codes_get(gid, 'Ni')
    nj = eccodes.codes_get(gid, 'Nj')
    lats = eccodes.codes_get_array(gid, 'latitudes')
    lons = eccodes.codes_get_array(gid, 'longitudes')
    print(len(lats))
    print(len(lons))
    # lat_grid = np.reshape(lats, (nj, ni))
    # lon_grid = np.reshape(lons, (nj, ni))
    eccodes.codes_release(gid)
    return lats, lons


def extract_indices_for_bbox(lat: np.ndarray, lon: np.ndarray, bboxs: List[tuple]) -> List[List[float]]:
    all_indices =[]

    for bbox in bboxs:
        """Extract data for a given bounding box."""
        lat_min, lat_max, lon_min, lon_max = bbox
        # Combined mask: points where BOTH lat AND lon are inside bbox
        mask = ((lat >= lat_min) & (lat <= lat_max) &
                (lon >= lon_min) & (lon <= lon_max))

        # Get indices of points inside Indiana
        latlon_indices = np.where(mask)[0]
        all_indices.append(latlon_indices)

    return all_indices

def get_lat_lon_for_indices(lat: np.ndarray, lon: np.ndarray, indices: List[int]) -> tuple:
    """Get latitudes and longitudes for given indices."""
    filtered_lat = lat[indices]
    filtered_lon = lon[indices]
    return filtered_lat, filtered_lon


def process_message(message, indices: List[int]) -> dict:
    """Function to process a single message."""
    try:
        # create a BitReader object
        bit_reader = bitreader_c.BitReader(message['raw_data'], initial_bit_offset=40)


        # get the first values of original scaled data
        try:
            first_values = extract_initial_values(message, bit_reader)
        except Exception as e:
            # put all values as 0
            unscaled_values = np.zeros(message['total_data_points'])
            
            return {
                'message_number': message['message_number'],
                'unscaled_values': unscaled_values
            }

        start_time = time.time()
        bit_group_reader = BitGroupReader(
            num_groups=message['number_of_groups_of_data_values'],
            num_bits=message['bitpervalue'],
            group_width_bits=message['number_of_bits_for_group_widths'],
            group_width=message['reference_for_group_widths'],
            group_length_increment=message['length_increment_for_the_group_lengths'],
            group_lengths_reference=message['reference_for_group_lengths'],
            group_scaled_length_bits=message['number_of_bits_for_scaled_group_lengths'],
            group_last_length=message['true_length_of_last_group']
        )
        bit_groups = bit_group_reader.read_groups(bit_reader)

        # check the lengths
        if not bit_group_reader.check_lengths(bit_groups, message['total_data_points'], len(message['raw_data'])):
            print("Error: Group lengths do not match the total number of data points.")
            return None

        # extract the data

        packed_values = extract_packed_values(bit_reader, bit_groups)
        del bit_groups
        del bit_reader

        # undo spatial differencing

        original_scaled_values = utils.undo_second_order_differencing(packed_values, first_values)
        filtered_original_scaled_values = original_scaled_values[indices]
        del original_scaled_values
        del packed_values

        # unscale the values
        unscaled_values = utils.unscale_values(filtered_original_scaled_values, message['binary_scale_factor'], message['decimal_scale_factor'], message['reference_value'])

        # Return results and timing information
        return {
            'name': message['parameter_name'],
            'message_number': message['message_number'],
            'unscaled_values': unscaled_values
        }

    except Exception as e:
        print(f"Error processing message {message['message_number']}: {e}")
        return None
    
def bbox_3km_center(lat: np.ndarray, lon: np.ndarray) -> tuple:
    """
    lat_c: latitude in degrees (e.g., 37.77327165)
    lon_c_0_360: longitude in 0–360 convention (e.g., 272.4791282439)
    Returns: (lat_min, lat_max, lon_min, lon_max) with lon in -180..180
    """
    # 1) Convert 0–360 lon to -180..180
    lon_converted = np.where(lon > 180, lon - 360.0, lon)

    # 2) Compute degree offsets for 1.5 km in each direction
    half_km = 1.5
    # Approximate conversions
    lat_deg_per_km = 1.0 / 111.2
    lon_deg_per_km = 1.0 / (111.2 * np.cos(np.radians(lat)))

    dlat = half_km * lat_deg_per_km
    dlon = half_km * lon_deg_per_km

    lat_min = lat - dlat
    lat_max = lat + dlat
    lon_min = lon_converted - dlon
    lon_max = lon_converted + dlon

    return lat_min, lat_max, lon_min, lon_max


def process_daily_results(daily_results: List[dict]) -> dict:
    intermediate = {}
    processed_data = {}
    for result in daily_results:
        if result is None:
            continue
        if not result.get('name',0):
            continue
        if result['name'] not in intermediate:
            intermediate[result['name']] = []
        intermediate[result['name']].append(result['unscaled_values'])
    
    for name, values in intermediate.items():
        array_values = np.array(values)
        max_values = np.max(array_values, axis=0)
        min_values = np.min(array_values, axis=0)
        mean_values = np.mean(array_values, axis=0)

        if "precipitation" in name.lower():
            processed_data[name] = np.sum(array_values, axis=0)
        else:
            processed_data[name + " max"] = max_values
            processed_data[name + " min"] = min_values
            processed_data[name + " mean"] = mean_values
        
    return processed_data


def save_results(date: str, results: dict, bbox_3km: tuple):

    year = date[:4]
    output_dir = f"../output/{year}"

    os.makedirs(output_dir, exist_ok=True)
    # Save results to a file
    filename = f"{output_dir}/{date}.csv"
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        cols = results.keys()
        writer.writerow(['lat_min', 'lat_max', 'lon_min', 'lon_max', *cols])

        for i, lat_min in enumerate(bbox_3km[0]):
            values =[]
            for col in cols:
                values.append(results[col][i])
            writer.writerow([lat_min, bbox_3km[1][i], bbox_3km[2][i], bbox_3km[3][i], *values])

def process_lat_lon(path: str):
    if not os.path.exists("../cache/lat_grid.npy") or not os.path.exists("../cache/lon_grid.npy"):
        lat, lon = load_lat_lon_grid(path)
        np.save("../cache/lat_grid.npy", lat)
        np.save("../cache/lon_grid.npy", lon)
    else:
        lat = np.load("../cache/lat_grid.npy")
        lon = np.load("../cache/lon_grid.npy")

    # indiana bbox
    bboxs = [(37.772, 41.761, 272.472, 275.216)]
    indices = extract_indices_for_bbox(lat, lon, bboxs)

    # record length of indices for each bbox
    indices_lengths = [len(idx) for idx in indices]
    print(indices_lengths)

    indices = [idx for sublist in indices for idx in sublist]

    filtered_lat, filtered_lon = get_lat_lon_for_indices(lat, lon, indices)
    return filtered_lat, filtered_lon, indices


def process_single_day(paths: List[str], date: str) -> dict:
    lat, lon, indices = process_lat_lon(paths[0])

    print("Processing date:", date)
    results = []
    try:
        start_time = time.time()
        for path in paths:
            # parse the GRIB file
            print("Parsing file:", path)
            messages = parse_grib_file(path, lat, lon)
            print("Parsed file:", path)
            for mesage in messages:
                result = process_message(mesage, indices)
                results.append(result)
            print("Processed file:", path)

            del messages
        parsing_time = time.time() - start_time
        print(f"Parsing time for date {date}: {parsing_time:.2f} seconds")

        # processing results
        processed_results = process_daily_results(results)
        del results

        # processing lat and lon values to get a bounding box of 3km around center
        bbox_3km = bbox_3km_center(lat, lon)

        print("Processed results for date:", date)
        save_results(date, processed_results, bbox_3km)

        del processed_results

    except Exception as e:
        print(f"Error processing date {date}: {e}")
        # Clean up partial results
        if 'results' in locals():
            del results
        if 'processed_results' in locals():
            del processed_results
        return {"date": date, "status": "failed", "error": str(e)}


def load_file_paths(root_data_dir: str) -> dict:
    filepath_dict_path = "../cache/filepaths_based_on_date.json"
    
    if not os.path.exists(filepath_dict_path):
        file_paths_based_on_date = {}
        
        for year_dir in os.listdir(root_data_dir):
            year_path = os.path.join(root_data_dir, year_dir)
            if not os.path.isdir(year_path):
                continue
                
            for date_dir in os.listdir(year_path):
                day_path = os.path.join(year_path, date_dir)
                if not os.path.isdir(day_path):
                    continue
                
                file_paths = [
                    os.path.join(day_path, f)
                    for f in os.listdir(day_path)
                    if f.endswith(".grib2")
                ]
                
                if file_paths:
                    file_paths_based_on_date[date_dir] = file_paths
        
        with open(filepath_dict_path, 'w') as f:
            json.dump(file_paths_based_on_date, f, indent=4)
    else:
        with open(filepath_dict_path, 'r') as f:
            file_paths_based_on_date = json.load(f)
    return file_paths_based_on_date

def main():

    print("\n\n")

    root_data_dir = "/mnt/yieldPrediction/wrf"

    if not os.path.exists("../cache"):
        print("Creating cache directory...")
        os.makedirs("../cache")
        print("Cache directory created.")

    file_paths_based_on_date = load_file_paths(root_data_dir)

    start_time = time.time()

    # for date, paths in file_paths_based_on_date.items():
    #     print(f"Date: {date}, Number of files: {len(paths)}")
    #     process_single_day(paths, date, lat, lon, indices)
    with concurrent.futures.ProcessPoolExecutor(max_workers=10) as executor:

        futures = [
            executor.submit(process_single_day, paths, date)
            for date, paths in file_paths_based_on_date.items()
        ]

        # processing results as they complete
        completed = 0
        total = len(futures)

        for future in concurrent.futures.as_completed(futures, timeout=600):
            completed += 1
            
            try:
                result = future.result(timeout=60)  # This is critical - must call result()
                print(f"[{completed}/{total}] Completed")
            except Exception as e:
                future.cancel()
                print(f"[{completed}/{total}] Failed: - Error: {e}")
            
            # Explicitly delete the future reference
            del future

    processing_time = time.time() - start_time
    print(f"Processing time for processing: {processing_time:.2f} seconds")
        
if __name__ == "__main__":
    main()
    