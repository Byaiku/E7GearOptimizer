import multiprocessing as mp
import os
import re
from itertools import product
from typing import List, Tuple, Dict

import cv2 as cv
import requests
from PIL import Image
from tesserocr import PyTessBaseAPI, PSM, OEM

from gear import *
import time

tesseract = PyTessBaseAPI(path='resources/tessdata', psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY, )


class E7GearOptimizer:
    def __init__(self):
        self.gears = []
        self.hero_loadouts = {}

        self.hero_base_stat = None

        self.optimizer_output = []

        self.__triangle = cv.imread('resources/ocr/triangle.jpg', 0)
        self.__top_bar = cv.imread('resources/ocr/top.jpg', 0)

        self.cores = mp.cpu_count() // 2 - 1

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        self.__dict__ = state

    def load(self):
        """
        Loads gears and saved hero loadouts if exists

        :return: None
        """
        if os.path.exists('gears.json'):
            with open('gears.json', 'r') as file_input:
                self.gears = json.load(file_input, object_hook=json_to_gear)

        if os.path.exists('hero_loadouts.json'):
            with open('hero_loadouts.json', 'r') as file_input:
                self.hero_loadouts = json.load(file_input)

    def save(self):
        """
        Saves gears and loadout

        :return: None
        """
        with open('gears.json', 'w') as file_output:
            json.dump(self.gears, file_output, cls=GearJSONEncoder, indent=2, separators=(',', ': '))

        with open('hero_loadouts.json', 'w') as file_output:
            json.dump(self.hero_loadouts, file_output, indent=2)

    @staticmethod
    def get_hero_list() -> Tuple[str]:
        """
        Gets all the current heroes in Epic Seven from epicsevendb.com

        :return: Tuple of current heroes
        """
        heroes = requests.get('https://api.epicsevendb.com/hero').json()
        heroes = tuple([hero['name'] for hero in heroes['results']])

        return heroes

    @staticmethod
    def get_hero_stats(hero: str) -> Dict[str, float]:
        """
        Gets the 6* fully awakened base stats of a hero from epicsevendb.com

        Stat calculation: https://github.com/EpicSevenDB/api/issues/2

        :param hero: hero name
        :return: Dictionary of the hero's base stats
        """

        pattern = re.compile(r'[\W_ ]+')
        hero = pattern.sub(' ', hero)
        data = requests.get('https://api.epicsevendb.com/hero/{}'.format('-'.join(hero.lower().split()))).json()
        stats = data['results'][0]['calculatedStatus']['lv60SixStarFullyAwakened']
        hero_base_stats = {
            'Attack': stats['atk'],
            'Defense': stats['def'],
            'Health': stats['hp'],
            'Speed': stats['spd'],
            'Crit. C': stats['chc'] * 100,
            'Crit. D': stats['chd'] * 100,
            'Eff': stats['eff'] * 100,
            'Eff. Resist': stats['efr'] * 100
        }

        return hero_base_stats

    def _ocr(self, image) -> str:
        """
        Performs OCR on image and returns output.

        :param image: image in numpy array format
        :return: OCR string
        """
        processed_image = cv.threshold(cv.resize(image, None, fx=5, fy=5), 50, 255, cv.THRESH_BINARY_INV)[1]
        tesseract.SetImage(Image.fromarray(processed_image))
        return tesseract.GetUTF8Text().strip()

    @staticmethod
    def _post_process_gear_type(gear_type: str) -> int:
        """
        Process the string passed from OCR and return the equipment type

        :param gear_type: gear type string passed from OCR
        :return: the equipment type
        """
        gear_type = gear_type.replace('Rina', 'Ring').lower()
        for g_type in GearType:
            if g_type.name.lower() in gear_type.lower():
                return g_type.value

        raise NameError('Unknown equipment type:', gear_type)

    @staticmethod
    def _post_process_gear_set(gear_set: str) -> int:
        """
        Process the string passed from OCR and return the equipment set

        :param gear_set: gear set string passed from OCR
        :return: the equipment set
        """
        gear_set = [x.lower() for x in gear_set.split()]
        for g_set in GearSet:
            if g_set.name.lower() in gear_set:
                return g_set.value

        raise NameError('Unknown equipment set:', gear_set)

    @staticmethod
    def _post_process_gear_stat(equip_stat: str) -> Stat:
        """
        Process the string passed from OCR and return a Stat object holding the stat and value

        :param equip_stat: stat string passed from OCR
        :return: Stat object
        """
        matched = re.findall(r'([^\d][a-zA-Z\s]+).*?([0-9]+%*)',
                             equip_stat.replace(',', '').replace('T%', '7%'))
        if matched:
            stat = -1
            if 'attack' in matched[0][0].lower():
                stat = GearStat.Attack.value
            if 'health' in matched[0][0].lower():
                stat = GearStat.Health.value
            if 'defense' in matched[0][0].lower():
                stat = GearStat.Defense.value
            if 'speed' in matched[0][0].lower():
                stat = GearStat.Speed.value
            if 'chance' in matched[0][0].lower():
                stat = GearStat.CritC.value
            if 'damage' in matched[0][0].lower():
                stat = GearStat.CritD.value
            if 'effectiveness' in matched[0][0].lower():
                stat = GearStat.Eff.value
            if 'resistance' in matched[0][0].lower():
                stat = GearStat.ER.value

            if stat == -1:
                raise NameError('Unknown equipment stat:', equip_stat)

            value = matched[0][1]
            if '%' in value and GearStat(stat) not in [GearStat.CritC, GearStat.CritD, GearStat.Eff, GearStat.ER]:
                is_flat = False
            else:
                is_flat = True
            value = int(value.replace('%', ''))
            return Stat(stat, value, is_flat)
        else:
            raise NameError('No matches from regex found for \'{}\''.format(equip_stat))

    def score_stat(self, stat: Stat) -> float:
        """
        Given a stat and value, return a score grading "how good" the stat is
        :param stat: Stat object
        :return: score of the stat
        """
        stat_type = GearStat(stat.type)
        if stat_type in [GearStat.CritC, GearStat.Speed]:
            return stat.value * 2
        elif stat_type in [GearStat.CritD]:
            return stat.value * 1.43
        elif stat.is_flat and stat_type not in [GearStat.Eff, GearStat.ER]:
            effective_percent = stat.value / self.hero_base_stat[GearStat(stat.type).name]
            return effective_percent * 1.25
        else:
            return stat.value * 1.25

    def score_gear(self, gear: Gear, required_sets, priorities):
        """
        Given a gear, return how good the gear is in terms of requirements set such as stat priority and set requirement

        :param gear: Gear equipment
        :param required_sets: Preferred sets
        :param priorities: Stat prioritization
        :return: score of the equipment
        """
        score = 0
        for i, priority in enumerate(priorities):
            if gear.main_stat.type == priority:
                score += self.score_stat(gear.main_stat) * (len(priorities) - i)

            for substat in gear.substats:
                if substat.type == priority:
                    score += self.score_stat(substat) * (len(priorities) - i)

        bonus = 1
        equip_set_bonus = Loadout.set_bonus(gear.set)
        if equip_set_bonus:
            bonus += self.score_stat(equip_set_bonus) / Loadout.set_requirement(gear.set) / 100

        if gear.set in required_sets:
            bonus += 1

        return score * bonus

    @staticmethod
    def score_final_stats(stats: Dict[str, int], priorities):
        """
        Given the final stats of a hero, return how good overall eDPS/eHP the stats are.

        NOTES: Will need to try other grading systems to see how well it sorts output. (e.g CP calculation)
        https://www.reddit.com/r/EpicSeven/comments/dvdfqp/guide_combat_power_calculation/

        :param stats: Final stats
        :param priorities: Stat prioritization
        :return: score of eDPS + eHP
        """
        dmg = 0
        crit = 1
        crit_dmg = 1
        hp = 1
        defense = 1
        eff = 1
        er = 1
        spd = 1

        for n, priority_stat in enumerate(priorities):
            if GearStat(priority_stat) == GearStat.Attack:
                dmg = stats['Attack'] / 1000
            elif GearStat(priority_stat) == GearStat.Health:
                hp = stats['Health'] / 10000
                if GearStat.Attack.value not in priorities:
                    dmg = stats['Health'] / 10000
            elif GearStat(priority_stat) == GearStat.CritC:
                crit = max(0, min(stats['Crit. C'], 100)) / 100
                crit = 1
            elif GearStat(priority_stat) == GearStat.CritD:
                crit_dmg = stats['Crit. D'] / 100 - 1
            elif GearStat(priority_stat) == GearStat.Defense:
                defense = (stats['Defense']) / 300 + 1
            elif GearStat(priority_stat) == GearStat.ER:
                er = stats['Eff. Resist']
            elif GearStat(priority_stat) == GearStat.Speed:
                spd = stats['Speed'] / 100
            elif GearStat(priority_stat) == GearStat.Effectiveness:
                eff = stats['Eff']

        e_dps = dmg * (1 + crit * crit_dmg)
        e_hp = (hp * defense) * er
        utility = eff

        return (e_dps + e_hp + utility) * spd

    def _import_gear_aux(self, image_paths: List[str], return_output=None):
        """
        Helper function for import_gear

        :param image_paths: List of image paths
        :param return_output: the shared output for multiprocessing
        :return:
        """
        output = []
        for path in image_paths:
            gear_image = cv.imread(path, 0)
            h, w = gear_image.shape
            gear_image = gear_image[60:h, 395:880]

            triangle = cv.matchTemplate(gear_image, self.__triangle, cv.TM_CCOEFF_NORMED)
            _, a, _, triangle_loc = cv.minMaxLoc(triangle)
            top = cv.matchTemplate(gear_image, self.__top_bar, cv.TM_CCOEFF_NORMED)
            _, b, _, top_loc = cv.minMaxLoc(top)

            # Box coordinates
            main_stat_box = (top_loc[0] + 30, top_loc[1] + self.__top_bar.shape[0],
                             top_loc[0] + self.__top_bar.shape[1], top_loc[1] + self.__top_bar.shape[0] + 52)
            substats_box = (top_loc[0], top_loc[1] + + self.__top_bar.shape[0] + 73,
                            top_loc[0] + self.__top_bar.shape[1], top_loc[1] + + self.__top_bar.shape[0] + 165)
            set_box = (substats_box[0] + 37, substats_box[3] + 25,
                       triangle_loc[0], substats_box[3] + 65)
            type_box = (triangle_loc[0] - 185, triangle_loc[1],
                        triangle_loc[0], triangle_loc[1] + 45)
            set_image = gear_image[set_box[1]:set_box[3], set_box[0]:set_box[2]]
            type_image = gear_image[type_box[1]:type_box[3], type_box[0]:type_box[2]]
            main_stat_image = gear_image[main_stat_box[1]:main_stat_box[3], main_stat_box[0]:main_stat_box[2]]
            substats_image = gear_image[substats_box[1]:substats_box[3], substats_box[0]:substats_box[2]]

            equip_type = self._ocr(type_image)
            equip_set = self._ocr(set_image)
            main_stat = self._ocr(main_stat_image)

            # Certain gears seems to have the gear type placed higher than usual, we retry except crop higher
            if len(equip_type) == 0:
                type_image = gear_image[type_box[1]:(type_box[3] - 5), type_box[0]:type_box[2]]
                processed_image = cv.threshold(cv.resize(type_image, None, fx=5, fy=5), 50, 255, cv.THRESH_BINARY_INV)[
                    1]
                tesseract.SetImage(Image.fromarray(processed_image))
                equip_type = tesseract.GetUTF8Text().strip()

            substats = []
            substat_height = int(substats_image.shape[0] / 4)
            for x in range(4):
                substat_image = substats_image[x * substat_height:(x + 1) * substat_height,
                                0:substats_image.shape[1]]
                substats.append(self._ocr(substat_image))

            gear = Gear(
                -1,
                self._post_process_gear_type(equip_type),
                self._post_process_gear_set(equip_set),
                self._post_process_gear_stat(main_stat),
                [self._post_process_gear_stat(sub) for sub in substats],
                False
            )
            output.append(gear)

        if return_output:
            return_output.put(output)

        return output

    def import_gear(self, image_paths: List[str]):
        """
        Import gear image into a Gear object and adds it to list of gears
        Image resolution must be in 1280x720 resolution.

        :param image_paths: list of image path or a string path
        :return: None
        """
        if len(image_paths) < self.cores:
            output = self._import_gear_aux(image_paths)
            for gear in output:
                gear.id = self.gears[-1].id + 1 if len(self.gears) != 0 else 0
                self.gears.append(gear)
        else:
            mp_output = mp.Queue(maxsize=self.cores)
            processes = []
            for x in range(self.cores):
                p = mp.Process(target=self._import_gear_aux, args=(image_paths[x + 1::self.cores + 1], mp_output))
                processes.append(p)
                p.start()

            output = self._import_gear_aux(image_paths[::self.cores + 1])

            # Get results and add to optimizer's list of gear
            results = [mp_output.get() for _ in processes]
            results.append(output)

            for result in results:
                for gear in result:
                    gear.id = self.gears[-1].id + 1 if len(self.gears) != 0 else 0
                    self.gears.append(gear)

            # Join processes
            for process in processes:
                process.join()
        self.save()

    def _optimize_aux(self, loadouts, priorities: List[str], required_sets: List[str],
                      min_max_constraints: Dict[str, tuple], output=None):
        """
        Helper function for optimize

        :param loadouts: List of loadouts combinations to check
        :param priorities: List of stats to focus on, priority based on position in list, 0 = highest
        :param required_sets: List of sets the loadout is required to have
        :param min_max_constraints: Final hero stats min-max constraints
        :param output: shared output for multiprocessing
        :return: Top 50 loadouts that meet the requirements
        """
        results = []
        for loadout in loadouts:
            loadout.post_init()

            # Skip if loadout doesn't contain the required sets
            if len(required_sets) != 0:
                if len(loadout.set) == 0:
                    continue
                else:
                    if not any(r_set in loadout.set for r_set in required_sets):
                        continue

            # Calculate hero's final stats
            final_stats = {}
            for stat, multipliers in loadout.stats_given.items():
                final_stats[stat] = int(self.hero_base_stat[stat] * (1 + multipliers[0] / 100) + multipliers[1])

            # Check if stats meet min-max constraints
            within_constraint = True
            for stat, min_max in min_max_constraints.items():
                if not (min_max[0] <= final_stats[stat] <= min_max[1]):
                    within_constraint = False

            # Add to output
            if within_constraint:
                results.append((final_stats, loadout))

        results.sort(key=lambda a: self.score_final_stats(a[0], priorities), reverse=True)
        results = results[:50]

        if output:
            output.put(results)
        return results

    def optimize(self, priorities: List[str], required_sets: List[str], min_max_constraints: Dict[str, tuple]):
        """
        Optimizes best gear loadout based on parameters passed in and saves it into a list before sorting the output
        list from best to worst using eDPS/eHP as a scoring
        factor.

        :param priorities: List of stats to focus on, priority based on position in list, 0 = highest
        :param required_sets: List of sets the loadout is required to have
        :param min_max_constraints: Final hero stats min-max constraints
        :return: None
        """
        # No hero selected
        if self.hero_base_stat is None:
            return
        if len(self.gears) == 0:
            return

        self.optimizer_output.clear()
        print("Starting optimizer")

        # Grab/sort/grade equips for smaller combination
        weapons = [x for x in self.gears if x.type == GearType.Weapon.value if not x.in_use]
        helmets = [x for x in self.gears if x.type == GearType.Helmet.value if not x.in_use]
        armors = [x for x in self.gears if x.type == GearType.Armor.value if not x.in_use]
        necklaces = [x for x in self.gears if x.type == GearType.Necklace.value if not x.in_use]
        rings = [x for x in self.gears if x.type == GearType.Ring.value if not x.in_use]
        boots = [x for x in self.gears if x.type == GearType.Boot.value if not x.in_use]

        weapons.sort(key=lambda x: self.score_gear(x, required_sets, priorities), reverse=True)
        helmets.sort(key=lambda x: self.score_gear(x, required_sets, priorities), reverse=True)
        armors.sort(key=lambda x: self.score_gear(x, required_sets, priorities), reverse=True)
        necklaces.sort(key=lambda x: self.score_gear(x, required_sets, priorities), reverse=True)
        rings.sort(key=lambda x: self.score_gear(x, required_sets, priorities), reverse=True)
        boots.sort(key=lambda x: self.score_gear(x, required_sets, priorities), reverse=True)

        # top 10 equipments, lowers combinations to 10^6
        weapons = weapons[:10]
        helmets = helmets[:10]
        armors = armors[:10]
        necklaces = necklaces[:10]
        rings = rings[:10]
        boots = boots[:10]

        loadouts = [Loadout(loadout) for loadout in product(weapons, helmets, armors, necklaces, rings, boots)]
        results = []

        if len(loadouts) < self.cores:
            output = self._optimize_aux(loadouts, priorities, required_sets, min_max_constraints)
            results.extend(output)
        else:
            mp_output = mp.Queue(maxsize=self.cores)
            processes = []
            for x in range(self.cores):
                p = mp.Process(target=self._optimize_aux, args=(loadouts[x + 1::self.cores + 1], priorities,
                                                                required_sets, min_max_constraints, mp_output))
                processes.append(p)
                p.start()

            output = self._optimize_aux(loadouts[::self.cores + 1], priorities, required_sets, min_max_constraints)
            results.extend(output)

            # Get results, sort and put top 50 into results
            for _ in processes:
                results.extend(mp_output.get())

            # Join processes
            for process in processes:
                process.join()

        results.sort(key=lambda a: self.score_final_stats(a[0], priorities), reverse=True)
        self.optimizer_output = results[:50]
        print("Finished optimization")

    def get_gear(self, gear_id: int) -> Gear:
        """
        Returns the gear given gear ID

        :param gear_id: ID of the gear
        :return: Gear with the given ID
        """
        start = 0
        end = len(self.gears) - 1
        while start <= end:
            idx = (start + end) // 2
            if self.gears[idx].id == gear_id:
                return self.gears[idx]
            elif self.gears[idx].id > gear_id:
                end = idx - 1
            else:
                start = idx + 1

        raise IndexError('Gear ID not found in inventory...')

    def set_gear_usage(self, gear_id: int, in_use: bool):
        """
        Sets the gear usage to either being in use or not

        :param gear_id: ID of gear
        :param in_use: whether it's in use or not
        :return None
        """
        start = 0
        end = len(self.gears) - 1
        while start <= end:
            idx = (start + end) // 2
            if self.gears[idx].id == gear_id:
                self.gears[idx].in_use = in_use
                return
            elif self.gears[idx].id > gear_id:
                end = idx - 1
            else:
                start = idx + 1

        raise IndexError('Gear ID not found in inventory...')
