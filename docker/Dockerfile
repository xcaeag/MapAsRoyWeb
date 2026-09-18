# https://gis.stackexchange.com/questions/462843/setting-up-qgis-python-scripts-in-docker-container

# Use an official QGIS image
FROM qgis/qgis:3.40

# Set environment variables for QGIS
ENV QGIS_PREFIX_PATH=/usr
ENV QT_QPA_PLATFORM=offscreen
ENV XDG_RUNTIME_DIR=/tmp/runtime-root
ENV LD_LIBRARY_PATH=/usr/local/lib:/usr/lib/grass83/lib

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app/

RUN apt update 
RUN apt -y upgrade
RUN rm -rf /var/lib/apt/lists/*

# Install any necessary Python dependencies from requirements.txt
COPY requirements.txt /app/
RUN cd /app
RUN pip install --no-cache-dir -r requirements.txt --ignore-installed --break-system-packages

EXPOSE 5000
CMD ["python3", "app.py"]
