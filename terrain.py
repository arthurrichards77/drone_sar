import numpy as np
import matplotlib.pyplot as plt

class TerrainTile:

    def __init__(self, filename):
        self.nrows = None
        self.ncols = None
        self.xllcorner = None
        self.yllcorner = None
        self.cellsize = None
        self.Z = None
        num_rows_read = 0
        with open(filename) as f:
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
        self.X, self.Y = np.meshgrid(np.arange(self.xllcorner,
                                               self.xllcorner+self.ncols*self.cellsize,
                                               self.cellsize),
                                    np.arange(self.yllcorner,
                                               self.yllcorner+self.nrows*self.cellsize,
                                               self.cellsize))

    def plot(self):
        fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
        # Plot the surface.
        surf = ax.plot_surface(self.X, self.Y, self.Z,
                               linewidth=0, antialiased=False)
        plt.show()

if __name__=='__main__':
    tile = TerrainTile('map_data/Download_llanbedr_terrain_2297518/terrain-5-dtm_5107396/sh/SH52NE.asc')
    tile.plot()