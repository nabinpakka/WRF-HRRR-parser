

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


def process_message(message, lat: np.ndarray, lon: np.ndarray, indices: List[int]) -> dict:
    """Function to process a single message."""
    try:
        # create a BitReader object
        bit_reader = bitreader_c.BitReader(message['raw_data'], initial_bit_offset=40)


        # get the first values of original scaled data
        try:
            start_time = time.time()
            first_values = extract_initial_values(message, bit_reader)
            initial_val_time = time.time() - start_time
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
        bit_group_extraction_time = time.time() - start_time

        # check the lengths
        if not bit_group_reader.check_lengths(bit_groups, message['total_data_points'], len(message['raw_data'])):
            print("Error: Group lengths do not match the total number of data points.")
            return None

        # extract the data
        start_time = time.time()
        packed_values = extract_packed_values(bit_reader, bit_groups)
        packed_value_extraction_time = time.time() - start_time

        # undo spatial differencing
        start_time = time.time()
        original_scaled_values = utils.undo_second_order_differencing(packed_values, first_values)
        spatial_differencing_time = time.time() - start_time

        # unscale the values
        start_time = time.time()
        unscaled_values = utils.unscale_values(original_scaled_values, message['binary_scale_factor'], message['decimal_scale_factor'], message['reference_value'])
        filtered_values = unscaled_values[indices]


        # get values for corresponding coordinates
        unscale_time = time.time() - start_time

        # Return results and timing information
        return {
            'name': message['parameter_name'],
            'message_number': message['message_number'],
            'unscaled_values': filtered_values
        }

    except Exception as e:
        print(f"Error processing message {message['message_number']}: {e}")
        return None

def process_results(daily_results: List[dict]) -> dict:
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


def save_results(date: str, results: dict, lat:np.ndarray, lon: np.ndarray):

    # Save results to a file
    filename = f"../cache/results_{date}.csv"
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        cols = results.keys()
        writer.writerow(['lat', 'lon', *cols])

        for i, l in enumerate(lat):
            values =[]
            for col in cols:
                values.append(results[col][i])
            writer.writerow([l, lon[i], *values])

def main():

    print("\n\n")

    root_data_dir = "../grib_data"

    # # unzip the grib_data folder if it does not exist
    # if not os.path.exists("../grib_data"):
    #     import zipfile
    #     with zipfile.ZipFile("../grib_data.zip", 'r') as zip_ref:
    #         print ("Unzipping the grib_data folder...")
    #         zip_ref.extractall("../")
    #     print("Unzipping complete.")

        # create the cache directory if it does not exist
    if not os.path.exists("../cache"):
        print("Creating cache directory...")
        os.makedirs("../cache")
        print("Cache directory created.")

    file_paths_based_on_date = {}
    filepath_dict_path =  "../cache/filepaths_based_on_date.json"
    if not os.path.exists(filepath_dict_path):

        # specify the filename
        for root, dirs, _ in os.walk(root_data_dir):
            for dir_name in dirs:
                date = dir_name
                file_paths = []
                for root, dirs, files in os.walk(os.path.join(root_data_dir, dir_name)):
                    for file_name in files:
                        if file_name.endswith(".grib2"):
                            file_path = os.path.join(root, file_name)
                            file_paths.append(file_path)
                file_paths_based_on_date[date] = file_paths
        with open(filepath_dict_path, 'w') as f:
            json.dump(file_paths_based_on_date, f, indent=4)
    else:
        with open(filepath_dict_path, 'r') as f:
            file_paths_based_on_date =  json.load(f)
    
    
    for date, paths in file_paths_based_on_date.items():
        # load lat/lon grids
        if not os.path.exists("../cache/lat_grid.npy") or not os.path.exists("../cache/lon_grid.npy"):
            lat, lon = load_lat_lon_grid(paths[0])
            np.save("../cache/lat_grid.npy", lat)
            np.save("../cache/lon_grid.npy", lon)
        else:
            lat = np.load("../cache/lat_grid.npy")
            lon = np.load("../cache/lon_grid.npy")

        daily_messages = []

        print(f"Date: {date}")
        for path in paths:
            print(f"  File: {path}")
    

            # parse the GRIB file
            messages = parse_grib_file(path, lat, lon)

            # number of messages
            print(f"Number of messages: {len(messages)}\n")
            daily_messages.extend(messages)

        # process messages sequentially
        start_time = time.time()

        bboxs = [(37.772, 41.761, 272.472, 275.216)]
        indices = extract_indices_for_bbox(lat, lon, bboxs)

        # record length of indices for each bbox
        indices_lengths = [len(idx) for idx in indices]
        print(indices_lengths)

        indices = [idx for sublist in indices for idx in sublist]
        daily_results = []
        for mesage in tqdm.tqdm(daily_messages):
            result = process_message(mesage, lat, lon, indices)
            daily_results.append(result)

        # processing results
        processed_results = process_results(daily_results)
        filtered_lat, filtered_lon = get_lat_lon_for_indices(lat, lon, indices)
        save_results(date, processed_results, filtered_lat, filtered_lon)
        processing_time = time.time() - start_time
        print(f"Processing time for {date} processing: {processing_time:.2f} seconds")
    
   
    
if __name__ == "__main__":
    main()
    