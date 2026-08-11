import numpy as np
def build(tape):
    features = tape.features()
    y = tape.truth(['menu_net_cent'])['menu_net_cent']
    x = np.concatenate([features['direct_raw'], features['grid_1s']], axis=0)
    return x, y
