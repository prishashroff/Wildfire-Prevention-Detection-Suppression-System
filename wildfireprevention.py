# -*- coding: utf-8 -*-
"""WildfirePrevention.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1d1q7JXLnPqXCcQd0sKNG_Q7xxUDqroQa
"""

#import files to load data
import descarteslabs as dl
import numpy as np
import pandas as pd
import geopandas
import descarteslabs.workflows as wf
import matplotlib.pyplot as plt
import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.model_selection import cross_val_score
from pyproj import Proj, transform
from shapely.ops import unary_union
from shapely.geometry import Point
from tqdm.notebook import tgdm

#set the time to time right now
end_datetimel = (datetime.datetime.utcnow())
start_datetimel = end_datetimel - datetime.timedelta(minutes = 15)
end_datetimel = (end_datetimel.isoformat())
start_datetimel = (start_datetimel.isoformat())
end_datetimel5 = (datetime.datetime.utcnow()- datetime.timedelta(minutes = 15))
start_datetimel5 = end_datetimel5 - datetime.timedelta(minutes = 15)
end_datetimel5 = (end_datetimel5.isoformat())
start_datetimel5 = (start_datetimel5.isoformat())
start_datetimel6 = start_datetimel5
end_datetimel6 = end_datetimel5

# Load landcover image coordinates which do not contain: open water, perennial ice/snow, Developed Land (open space, Low intensity, medium intensity, high intensity, barren land (Rock, sand, clay), moss, woody wetlands and emergent herbaceous wetlands.

# Stiches all the images of the world into a map so it is easy for visualization, along with loading the dataset
img = wf.ImageCollection.from_id('nlcd:land_cover').mosaic()
# Creating a mask for the data and points that should not be included in the classifier
unwanted_areas = (img == 11) | (img == 12) | (img == 31) | (img == 90) | (img == 21) | (img == 22) | (img == 23) | (img == 24) | (img == 95) | (img == 74)
imgl = img.mask(unwanted_areas)


# Load precipitation image coordinates which do not have any rainfall at all

gfs = wf.ImageCollection.from_id('ncep:gfs:vl', start_datetime=start_datetimel5, end_datetime=end_datetimel5).mosaic()
#this Line chooses the specific type of data it needs from the dataset (weather dataset, precipitation specifically)
precipitation = gfs.pick_bands('PRATE_0-SFC')
precipitation_mask = (precipitation > 0)

#load wind image coordinates which have enough wind for the fire to spread

#chooses the specific type of data it needs from the dataset (weather dataset, wind speed specifically)
wind = gfs.pick_bands('GUST_0-SFC')
#load soil moisture image coordinates
soilmoisture = gfs.pick_bands('SOILW_0-0p1-DBLL')

#load vegetation image coordinates
modis = wf.ImageCollection.from_id('modis:09:v2', start_datetime=start_datetimel, end_datetime=end_datetimel).mosaic()
# The next 2 lines choose the specific type of data it needs from the dataset (modis(earthdata) dataset, ndvi specifically)
nir = modis.pick_bands('nir')
red = modis.pick_bands('red')
ndvi = (nir - red) / (nir + red)
#creating a mask for the data which takes out areas with no/minimum vegetation and heavily wet vegetation
ndvi_mask = (1.5 > ndvi > -0.5)
#load temperature image coordinates
normaltemp = modis.pick_bands('thermal2')
#load temperature image coordinates
abnormaltemp = modis.pick_bands('thermal1')


preventionmasks = unwanted_areas | precipitation_mask | ndvi_mask
preventioncombined_data = precipitation.concat_bands(wind).concat_bands(ndvi).concat_bands(soilmoisture).concat_bands(normaltemp).concat_bands(abnormaltemp)
preventioncombined_data = preventioncombined_data.mask(preventionmasks)

#reads data for classifier
df = preventioncombined_data
values = df.values[:, :]
X = values[:, :-1]
y = values[:, -1]

# Spliting the dataset into testing and training data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

# Setting up the classifier and the data
clf = RandomForestClassifier(n_estimators=7, max_depth = 5, random_state=0).fit(X_train, y_train)

# Testing the model and evalutaing the model
y_test_pred = clf.predict(X_test)
print(accuracy_score(y_test, y_test_pred))
y_train_pred = clf.predict(X_train)
print(accuracy_score(y_train, y_train_pred))
accuracy = cross_val_score(clf, X, y, scoring='accuracy', cv = 10)
#get the mean of each fold
print("Accuracy of Model with Cross Validation is:", accuracy.mean() * 100)

# Download data on the map
places_client = dl.Places()
united_states = places_client.shape('conus')
res = preventioncombined_data.compute(dl.scenes.AOI(united_states,crs='EP5G:4326', resolution = 0.5))

arr = res.ndarray
ctx = res.geocontext

# Reshaping in preparation for the model
arr = np.moveaxis(arr, 0, -1)
arr = arr.reshape((arr.shape[0] * arr.shape[1], arr.shape[2]))

# Creating a mask of good data
good_data_mask = ~np.any(np.ma.getmaskarray(arr), axis=1)

# Getting coordinates for each pixel
gt = ctx['gdal_geotrans']
height, width = ctx['arr_shape']
x_wm = (np.arange(0, width) + 0.5) * gt[1] + gt[0]
y_wm = (np.arange(0, height) + 0.5) * gt[5] + gt[3]
xx_wm, yy_wm = np.meshgrid(x_wm, y_wm)
xx_wm = xx_wm.reshape((xx_wm.shape[0] *  xx_wm.shape[1]))
yy_wm = yy_wm.reshape((yy_wm.shape[0] * yy_wm.shape[1]))
arr = arr[good_data_mask, :]
xx_wm = xx_wm[good_data_mask]
yy_wm = yy_wm[good_data_mask]

# Running data through the model to get predictions
if arr.shape[0] > 0:
  predictions = clf.predict(arr)
  xx_wm_pos = xx_wm[predictions == 1]
  yy_wm_pos = yy_wm[predictions == 1]
  if xx_wm_pos.size > 0:
    lon, lat = transform(Proj(init='epsg:3857'), Proj(init='epsg:4326'), xx_wm_pos, yy_wm_pos)
    lat_lons = np.stack((lat, lon), axis=1)
    lat_lons = np.unique(np.round(lat_lons * 1e1) / 1e1, axis=0)
    print(lat_lons)
  else:
    print("There are no hotpots found")
else:
  print("All data masked.")

# Outputting coordinates
#filter out areas where wildfires are not allowed to be sprayed

gdf = geopandas.read_file('zip://5_USA.AerialFireRetardantAvoidance.zip')

lat_lons_filtered = []
for lat_lon in tgdm(lat_lons):
  pt = Point(lat_lon[1], lat_lon[0])
  keep_pt = True
  for geom in gdf.geometry.values:
    if geom.contains(pt):
      keep_pt = False
      break
  if keep_pt:
    lat_lons_filtered.append(lat_lon)
lat_lons_filtered = np.array(lat_lons_filtered)

#saving the filtered coordinates
lat_lons_filtered
np.savetxt('filteredcoordinates.txt', lat_lons_filtered)