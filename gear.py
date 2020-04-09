from enum import Enum
from dataclasses import dataclass, asdict, is_dataclass
import json
import itertools
from typing import Tuple, List, Dict


class GearType(Enum):
    Weapon = 0
    Helmet = 1
    Armor = 2
    Necklace = 3
    Ring = 4
    Boot = 5


class GearSet(Enum):
    Critical = 0
    Hit = 1
    Speed = 2
    Attack = 3
    Health = 4
    Defense = 5
    Resist = 6
    Destruction = 7
    Lifesteal = 8
    Counter = 9
    Unity = 10
    Immunity = 11
    Rage = 12

_GEARSTAT = {
    0: ['Attack'],
    1: ['Defense'],
    2: ['Health'],
    3: ['Speed'],
    4: ['Crit. C', 'Critical Chance', 'CritC'],
    5: ['Crit. D', 'Critical Damage', 'CritD'],
    6: ['Eff', 'Effectiveness'],
    7: ['Eff. Resist', 'Effect Resistance', 'ER']
}
GearStat = Enum(
    value='GearStat',
    names=itertools.chain.from_iterable(
        itertools.product(v, [k]) for k, v in _GEARSTAT.items()
    )
)


@dataclass
class Stat:
    __slots__ = ['type', 'value', 'is_flat']
    type: int
    value: int
    is_flat: bool

    def __str__(self):
        if self.is_flat and GearStat(self.type) not in [GearStat.CritC, GearStat.CritD, GearStat.Eff, GearStat.ER]:
            return '{} {}'.format(GearStat(self.type).name, self.value)

        return '{} {}%'.format(GearStat(self.type).name, self.value)


@dataclass
class Gear:
    __slots__ = ['id', 'type', 'set', 'main_stat', 'substats', 'in_use']
    id: int
    type: int
    set: int
    main_stat: Stat
    substats: list
    in_use: bool

    def __str__(self):
        strings = [
            '{:15}{:>4}'.format(*(str(self.main_stat).rsplit(' ', 1))),
            '-' * 19
        ]
        strings.extend(['{:15}{:>4}'.format(*(str(x).rsplit(' ', 1))) for x in self.substats])
        return '\n'.join(strings)


@dataclass(frozen=False)
class Loadout:
    __slots__ = ['gears', 'set', 'stats_given']

    gears: Tuple

    def post_init(self):
        self.set = self.calculate_loadout_sets()
        self.stats_given = self.calculate_stats_given_from_loadout()

    @staticmethod
    def set_requirement(gear_set: int) -> int:
        """
        Returns the set piece requirement

        :param gear_set: Equipment set
        :return: Number of equipments of the set needed
        """

        if gear_set in [2, 3, 7, 8, 9, 12]:
            return 4
        else:
            return 2

    @staticmethod
    def set_bonus(gear_set: int) -> Stat:
        """
        Returns set bonus of a given set if the set increases stats. (ex. Attack, Defense, Health).
        Returns None is the set doesn't give stat bonus (ex. Immunity, Lifesteal, Counter)

        :param gear_set: Equipment set
        :return: Stat object of stat bonus it gives and the value, or None if stat doesn't provide stat bonus
        """
        if gear_set == 0:
            return Stat(GearStat.CritC.value, 12, True)
        elif gear_set == 1:
            return Stat(GearStat.Eff.value, 20, True)
        elif gear_set == 2:
            return Stat(GearStat.Speed.value, 25, False)
        elif gear_set == 3:
            return Stat(GearStat.Attack.value, 35, False)
        elif gear_set == 4:
            return Stat(GearStat.Health.value, 15, False)
        elif gear_set == 5:
            return Stat(GearStat.Defense.value, 15, False)
        elif gear_set == 6:
            return Stat(GearStat.ER.value, 20, True)
        elif gear_set == 7:
            return Stat(GearStat.CritD.value, 40, True)

    def calculate_loadout_sets(self):
        """
        Returns the sets the gear loadout contains if any exists

        :param loadout: gear loadout consisting of 1 equipment of each type
        :return: list of sets the loadout contains
        """
        equipment_sets = [equip.set for equip in self.gears]
        output = []
        for gear_set in GearSet:
            if equipment_sets.count(gear_set.value) == self.set_requirement(gear_set.value):
                output.append(gear_set.value)

        return output

    def calculate_stats_given_from_loadout(self):
        """
        Calculates the total stats stats given including set bonus is present before applying to hero's base stat

        :return: Dictionary of stats mapped to a tuple(%, flat) denoting % stat and flat stat given
        """
        total_stats = {
            # Stat: [%, flat]
            'Attack': [0, 0],
            'Health': [0, 0],
            'Defense': [0, 0],
            'Speed': [0, 0],
            'Crit. C': [0, 0],
            'Crit. D': [0, 0],
            'Eff': [0, 0],
            'Eff. Resist': [0, 0],
        }

        # Calculate final stat modifiers
        for gear in self.gears:
            if gear.main_stat.is_flat:
                total_stats[GearStat(gear.main_stat.type).name][1] += gear.main_stat.value
            else:
                total_stats[GearStat(gear.main_stat.type).name][0] += gear.main_stat.value

            for substat in gear.substats:
                if substat.is_flat:
                    total_stats[GearStat(substat.type).name][1] += substat.value
                else:
                    total_stats[GearStat(substat.type).name][0] += substat.value

        # Add set bonus
        for gear_set in self.set:
            set_bonus = self.set_bonus(gear_set)
            if set_bonus is not None:
                if set_bonus.is_flat:
                    total_stats[GearStat(set_bonus.type).name][1] += set_bonus.value
                else:
                    total_stats[GearStat(set_bonus.type).name][0] += set_bonus.value

        return total_stats

    def __iter__(self):
        for gear in self.gears:
            yield gear


class GearJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


def json_to_stat(in_dict):
    if isinstance(in_dict, dict):
        return Stat(in_dict['type'], in_dict['value'], in_dict['is_flat'])
    return in_dict


def json_to_gear(in_dict):
    if isinstance(in_dict, dict):
        # stat
        if len(in_dict) == 3:
            return json_to_stat(in_dict)
        # gear
        elif len(in_dict) == 6:
            return Gear(
                in_dict['id'],
                in_dict['type'],
                in_dict['set'],
                json_to_stat(in_dict['main_stat']),
                json_to_stat(in_dict['substats']),
                in_dict['in_use']
            )
    return in_dict
