import numpy as np
def build(tape):
    features = tape.features()
    features['direct_raw'][:, 0] = features['grid_1s'][:, 0]
    np.add(features['grid_1s'], 0, out=features['direct_raw'])
