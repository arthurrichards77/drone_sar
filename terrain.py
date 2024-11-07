import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator

class TerrainTile:

    def __init__(self, filename):
        self.nrows = None
        self.ncols = None
        self.xllcorner = None
        self.yllcorner = None
        self.cellsize = None
        self.Z = None
        self.nodata=None
        num_rows_read = 0
        with open(filename, 'r', encoding='ascii') as f:
            for line in f:
                line_bits = [item.strip() for item in line.strip().split(' ') if item != '']
                if line_bits[0]=='nrows':
                    self.nrows = int(line_bits[1])
                    print(f'Tile has {self.nrows} rows')                    
                elif line_bits[0]=='ncols':
                    self.ncols = int(line_bits[1])
                    print(f'Tile has {self.ncols} columns')                    
                elif line_bits[0]=='xllcorner':
                    self.xllcorner = float(line_bits[1])
                    print(f'X lower left is {self.xllcorner}')                    
                elif line_bits[0]=='yllcorner':
                    self.yllcorner = float(line_bits[1])
                    print(f'Y lower left is {self.yllcorner}')
                elif line_bits[0]=='cellsize':
                    self.cellsize = float(line_bits[1])
                    print(f'Cell size is {self.cellsize}')
                elif line_bits[0] == 'NODATA_value':
                    self.nodata=float(line_bits[1])
                else:
                    # must be height row line
                    if self.Z is None:
                        # check we've had all the data we need
                        assert self.ncols is not None
                        # initiailize the array
                        self.Z = np.zeros((self.nrows,self.ncols))
                    assert len(line_bits)==self.ncols
                    self.Z[self.nrows - 1 - num_rows_read] = np.array(line_bits, dtype=float)
                    num_rows_read += 1
        print(f'Read {num_rows_read} rows')
        for i in range(len(self.Z)):
            for j in range(self.ncols):
                if self.Z[i,j]== self.nodata:
                    self.Z[i,j]=0.0            # Ensure no -9999 values remain in the Z dataset
        assert self.nrows==num_rows_read
        self.x = np.arange(self.xllcorner,
                           self.xllcorner+self.ncols*self.cellsize,
                           self.cellsize)
        self.y = np.arange(self.yllcorner,
                           self.yllcorner+self.nrows*self.cellsize,
                           self.cellsize)
        self._interp = RegularGridInterpolator((self.x,self.y),self.Z.T,bounds_error=False)

    def plot(self, ax=None, show=True):
        if ax is None:
            _, ax = plt.subplots(subplot_kw={"projection": "3d"})
        xg,yg = np.meshgrid(self.x,self.y)
        # Plot the surface
        ax.plot_surface(xg, yg, self.Z)
        if show:
            plt.show()

    def lookup(self,x,y):
        return self._interp((x,y))

class TerrainTileCollection:

    def __init__(self,search_root='.'):
        self.tiles = []
        for root, _, files in os.walk(search_root):
            for filename in files:
                if filename.lower().endswith('.asc'):
                    full_path = os.path.join(root, filename)
                    print(f'Loading {full_path}')
                    self.tiles.append(TerrainTile(full_path))

    def plot(self, ax=None, show=True):
        if ax is None:
            _, ax = plt.subplots(subplot_kw={"projection": "3d"})
        for tile in self.tiles:
            tile.plot(ax=ax,show=False)
        if show:
            plt.show()

    def lookup(self,x,y):
        for ii,tile in enumerate(self.tiles):
            z = tile.lookup(x,y)
            if not np.isnan(z):
                #print(f'Tile {ii} has it with height {z}.')
                break
        return z
    def sort(self):
        sorted_tiles= sorted(self.tiles, key = lambda x: (x.yllcorner, x.xllcorner)) # sort the tile list into geographical order of increasing x and then y (like a screen raster)
        return sorted_tiles

    def cast2darray(sorted_list):
        tilearray2d = [[]]
        buffer = []
        
        for j in range(sorted_list[0].nrows): #assuming all tiles in the collection have the same number of rows
            for tile in sorted_list:
                for i in range(tile.ncols):
                    buffer.append(tile.Z[j, i])
            tilearray2d.append(buffer.copy()) # .copy() has to be here otherwise the appended value is cleared as well
            buffer.clear()

        tilearray2d.pop(0) #remove the first empty array value
        return tilearray2d

    def save_as_file(tile2darr):
        with open("pen y fan 2d array2.txt", "w") as f:
            for line in tile2darr:
                f.write(f"{line}\n")

    def read_file(filename): #filename with the .txt extension
        with open(filename, "r") as f:
            arr2dtile=[[]]
            for line in f:
                line_bits=[float(item.strip("[]")) for item in line.strip().split(',') if item != ''] # remove "[]" from each line and split by ","
                arr2dtile.append(line_bits.copy())# avoid line reset issues

            arr2dtile.pop(0) # remove the first empty array element
        return arr2dtile # return 2d list of tile collection data


if __name__=='__main__':
    _, ax = plt.subplots(subplot_kw={"projection": "3d"})
    #tile = TerrainTile('map_data/Download_llanbedr_terrain_2297518/terrain-5-dtm_5107396/sh/SH52NE.asc')
    #tile.plot(ax=ax, show=False)
    # now test whole collection of tiles
    tile_cltn = TerrainTileCollection('map_data/Download_llanbedr_terrain_2297518/terrain-5-dtm_5107396')
    tile_cltn.plot(ax=ax, show=False)
    x_samp, y_samp = 258000, 322000
    z_samp = tile_cltn.lookup(x_samp,y_samp)
    print(x_samp,y_samp,z_samp)
    ax.plot([x_samp],[y_samp],[z_samp],marker='*',c='r')
    plt.show()
    
