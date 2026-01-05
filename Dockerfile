# Use a base image with Miniconda installed
FROM continuumio/miniconda3:latest

# Set the working directory
WORKDIR /grib_parser

# Install ecCodes via apt (and any other packages you may need)
RUN apt-get update && apt-get install -y libeccodes-dev

# Copy the environment.yml file to the container
COPY environment.yml /grib_parser/environment.yml

# Install the conda environment with the required packages
RUN conda env create -f environment.yml

# Activate the environment
RUN echo "source activate grib" > ~/.bashrc
ENV PATH /opt/conda/envs/grib/bin:$PATH

# Copy the rest of the project files into the container
COPY . /grib_parser

# Ensure permissions on the copied files
RUN chmod -R 755 /grib_parser


