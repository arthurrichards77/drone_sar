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
        num_rows_read = 0
        with open(filename, 'r', encoding='ascii') as f:
            for line in f:
                line_bits = [item.strip() for item in line.split(' ')]
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

    def plot_tiles(self, ax=None, show=True):
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
    
    def to_nparray(self):
        """
        x,y,z = tile_collection.to_nparray()

        x and y are 1-D vectors with the grid coordinates
        z is a 2-D array with the terrain heights
        """
        # quick version for now, assuming same spacings
        all_x = np.unique(np.concatenate([t.x for t in self.tiles]))
        all_y = np.unique(np.concatenate([t.y for t in self.tiles]))
        all_z = np.zeros((len(all_y),len(all_x)))
        for t in self.tiles:
            x_idx = [x in t.x for x in all_x]
            y_idx = [y in t.y for y in all_y]
            all_z[np.ix_(y_idx,x_idx)] = t.Z
        return all_x, all_y, all_z
    
    def plot(self, ax=None):
        if ax is None:
            _, ax = plt.subplots(subplot_kw={"projection": "3d"})
        x,y,z = self.to_nparray()
        xg,yg = np.meshgrid(x,y)
        ax.plot_surface(xg, yg, z)
        plt.show()

if __name__=='__main__':
    #tile = TerrainTile('map_data/Download_llanbedr_terrain_2297518/terrain-5-dtm_5107396/sh/SH52NE.asc')
    #tile.plot(ax=ax, show=False)
    # now test whole collection of tiles
    tile_cltn = TerrainTileCollection('map_data/Download_llanbedr_terrain_2297518/terrain-5-dtm_5107396')
    tile_cltn.plot()
    x_samp, y_samp = 258000, 322000
    z_samp = tile_cltn.lookup(x_samp,y_samp)
    print(x_samp,y_samp,z_samp)
    
    


    