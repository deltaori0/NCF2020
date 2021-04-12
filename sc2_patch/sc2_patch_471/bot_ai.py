

from sc2.units import Units


@property
def known_enemy_units(self) -> Units:
    """List of known enemy units, including structures."""
    return self.state.enemy_units


@property
def known_enemy_structures(self) -> Units:
    """List of known enemy units, structures only."""
    return self.state.enemy_units.structure