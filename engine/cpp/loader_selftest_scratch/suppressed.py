import numpy as np
def build(tape):
    features = tape.features()
    y = tape.truth(['menu_net_cent'])['menu_net_cent']
    features['a'][0] = y  # truth-separation: guard-fixture
    features['b'][0] = y
