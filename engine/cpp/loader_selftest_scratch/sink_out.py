import numpy as np
def build(tape):
    features = tape.features()
    y = tape.truth(['menu_net_cent'])['menu_net_cent']
    np.add(y, 0, out=features['direct_raw'])
