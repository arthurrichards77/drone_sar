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
        with open(filename, 'r') as f:
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
        self.interp = RegularGridInterpolator((self.x,self.y),self.Z.T,bounds_error=False)

    def plot(self, ax=None, show=True):
        if ax is None:
            _, ax = plt.subplots(subplot_kw={"projection": "3d"})
        xg,yg = np.meshgrid(self.x,self.y)
        # Plot the surface
        surf = ax.plot_surface(xg, yg, self.Z,
                               linewidth=0, antialiased=True)
        if show:
            plt.show()


if __name__=='__main__':
    tile = TerrainTile('map_data/Download_llanbedr_terrain_2297518/terrain-5-dtm_5107396/sh/SH52NE.asc')
    _, ax = plt.subplots(subplot_kw={"projection": "3d"})
    tile.plot(ax=ax, show=False)
    x_samp, y_samp = 259900, 328000
    z_samp = tile.interp((x_samp,y_samp))
    print(x_samp,y_samp,z_samp)
    ax.plot([x_samp],[y_samp],[z_samp],marker='*',c='r')
    plt.show()