# Grib Parser and Decoder

## Overview
This project is designed to parse and decode grib files from byte data. 
The messages are first parsed via the byte data to extract the important values, then decoded.
Parsing the byte data currently takes the most time and to be improved.

An implementation in C++ will come soon.

## Prerequisites
- [Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) should be installed on your system.

## Setting Up the Environment

### 1. Clone the Repository
First, clone the project repository to your local machine:

```bash
git clone https://github.com/brycetur21/grib_parser.git
cd grib_parser/
```

### 2. Create the Conda Environment and Activate
To set up the project environment, create a new conda environment from the provided environment.yml file and activate it

```bash
conda env create -f environment.yml
conda activate grib
```

## Running the Code
 
### 1. Navigate to the src/ Directory
```bash
cd src/
python main.py
```


