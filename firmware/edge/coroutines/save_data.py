import json
counter = 0 

# Function to append an entry to a JSON file
# The file is created if it does not exist, and the entry is appended in JSON format
# The file is opened in append mode, and the first entry is written with a leading "["
def append_to_json_file(filename, entry):
    global counter

    #  Write the entry to the file
    with open(filename, 'a') as f:
        if counter == 0:
            f.write("[")
        json.dump(entry, f)
        f.write(",\n")
    
    counter += 1

# Function to get a unique filename by checking if the file already exists
# If the file exists, it appends a number to the base name until a unique name is found
# The default base name is "imu_data"
# Returns the unique filename
def get_unique_filename(base_name="imu_data"):
    i = 1
    while True:
        filename = f"{base_name}_{i}.json"
        try:
            with open(filename, "r"):
                pass
        except OSError:
            return filename
        i += 1

# Coroutine to save data to a JSON file
# It waits for data from the processor queue and appends it to the file
# The file name is generated using get_unique_filename
async def save_data_processor(processor_q, file_name):
    while True:
        results = await processor_q.get()
        append_to_json_file(file_name, results)