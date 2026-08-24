from requests import get
from typing import List, Set, Dict
import pprint as pp
import re
import argparse
import time
import datetime

DEBUGGER = False
DEBUG = lambda x: print(x) if DEBUGGER else None
PDEBUG = lambda x: pp.pprint(x) if DEBUGGER else None

## Colors for text coloring
RED     = '\033[31m'
REDB    = '\033[31;1m'
REDBB   = '\033[31;1;4m'
REG     = '\033[33;1m'
GRE     = '\033[32m'
FORCED  = '\033[34;1mforced - '
NFORCED = '\033[34;1m'
END     = '\033[0m'

# Defines class for price checking, avoiding excessive fetching, while also providing up-to-date prices.
class scarab_regexer():

    __last_update: float = 0
    __last_update_datetime = datetime.datetime.now()
    __char_limit: int = 250
    __value_threshold: float = 1.0

    def __init__(self, force_keep: List[str] = []):
        self.force_keep = force_keep
        self.get_prices()

    def update_char_limit(self, new_limit: int):
        new_limit = int(new_limit)
        if new_limit >= 0:
            self.__char_limit = new_limit
        else:
            DEBUG(f"Invalid char limit: {new_limit}. Must be a positive integer.")

    def update_value_threshold(self, new_threshold: float):
        self.__value_threshold = float(new_threshold)
        self.update_lists()

    def get_last_updated(self) -> str:
        return self.__last_update_datetime
    
    def get_threshold(self):
        return self.__value_threshold

    def print_forced(self):
        print(f"{NFORCED}Scarabs forced to be kept:{END}")
        print(f"{GRE}-","\n-".join(self.forced), f"{END}\n", sep="")

    def get_prices(self):
        now = time.time()
        # checks if last update was more than 10 minutes ago, or if an update is forced
        if (now - self.__last_update > 600):
            DEBUG("Updating pricelist...")
             # Dynamically get the name of the current league
            self.league = get("https://poe.ninja/poe1/api/data/index-state").json()["economyLeagues"][0]["name"]
            # Get the updated price of each scarab in chaos
            self.db = get(f"https://poe.ninja/poe1/api/economy/exchange/current/overview?league={self.league}&type=Scarab").json()
            self.names_clean: Dict[str, str] = {item["id"]: item["name"] for item in self.db["items"]}
            self.names = {id: f"^{name.lower()}$" for id, name in self.names_clean.items()}
            self.prices: Dict[str, float] = {self.names[item["id"]]: item["primaryValue"] for item in self.db["lines"]}
            # Sort price list from cheapest to most expensive
            self.prices = {it[0]: it[1] for it in sorted(self.prices.items(), key=lambda x: x[1])}
            self.__last_update = now
            self.__last_update_datetime = datetime.datetime.now()
            self.update_lists()
    
    # updates the keep, sell and forced lists
    def update_lists(self):
        self.get_prices()
        self.forced  = [name for name, _     in self.prices.items() if any(re.search(p.lower(), name[1:-1]) is not None for p in self.force_keep)]
        self.sell    = [name for name, value in self.prices.items() if value < self.__value_threshold and name not in self.forced]
        self.keep    = [name for name, _     in self.prices.items() if name not in self.sell]
        # removes the ^$ from the forced names, for readability
        self.forced  = [f[1:-1] for f in self.forced]

    # updates the force_keep list.
    def change_force_keep(self, new_force_keep: List[str]):
        self.force_keep = new_force_keep
        self.update_lists()
    
    # prints the current price list to terminal
    def print_prices(self, print_now = True, _price_overload: Dict[str,float] = {}) -> str:
        self.get_prices()
        printvar = ""
        printvar += f"{REDBB}Price list:{END}\n"

        pricelist = self.prices.items() if not _price_overload else _price_overload.items()

        # Control Constants
        longest_scarab_name_len = len(max([p[0] for p in pricelist], key=lambda x: len(x)))

        price_list_clean = [[name.replace("^","").replace("$",""), price] for name, price in pricelist]
        for name, price in price_list_clean:
            if price >= self.__value_threshold:
                color = GRE
                ncolor = END
            elif any(fk == name for fk in self.forced):
                ncolor = NFORCED
                color = FORCED
            else:
                color = RED
                ncolor = END
            printvar+=f"{ncolor}{name.replace("^","").replace("$",""): <{longest_scarab_name_len}}{END} {color}{price}c{END}\n"
        printvar+=f"{REDB}---------------------{END}\n"
        print(printvar) if print_now else None
        return printvar

    # gets all possible regexes that are in the include list but not in exclude list
    def __get_all_regexes(self, includes: List[str], excludes: List[str], anchor_word = "scarab") -> Dict[str, List[str]]:
        
        # Concatenate all the names of the scarabs to exclude so it is easier to check if a sub-string is present
        full_exclude = ",".join(excludes)
        # Save all the regexes that uniquely select the scarabs to keep
        regexes = {}
        # Get the shortest string in the name of each highlight scarab that is not present in the names of the scarabs to exclude
        for name in includes:
            for size in range(len(anchor_word) + 2, len(name) + 1):
                for start in range(len(name) - size + 1):
                    match = name[start:start+size]
                    if anchor_word in match and match not in full_exclude:
                        regexes.setdefault(name, []).append(match)
            if name not in regexes: raise Exception(f"No regex found for '{name}'")
        PDEBUG(regexes)
        return regexes

    def __get_best_regexes(self, reverse_match = True, anchor_word = "scarab", _incl: List[str] = [], _excl: List[str] = []) -> Set[str]:
        includes = self.sell if not _incl else _incl
        excludes = self.keep if not _excl else _excl
        includes, excludes = (excludes, includes) if reverse_match else (includes, excludes)
        
        # Create dict with all possible regexes for each item, anchored to anchor_word
        regexes = self.__get_all_regexes(includes, excludes, anchor_word=anchor_word)
        
        # Check how many scarabs would be selected by each regex
        regex_count = {}
        for name, data in regexes.items():
            for regex in data:
                regex_count[regex] = regex_count.get(regex, 0) + 1
        # Assign a weight/score for each regex based on how many scarabs they select and how long they are
        regex_score = {regex: len(regex) - count - (5 if regex.startswith(f"^{anchor_word}") or regex.startswith(anchor_word) or regex.endswith(anchor_word) or regex.endswith(f"{anchor_word}$") else 0) for regex, count in regex_count.items()}
        
        # Find the best regex for all scarabs by finding the scarab with the worst best regex and setting that as the regex for that scarab
        # Then all the other scarabs that also have that regex will use that regex, repeat untill all scarabs have regexes
        to_assing = includes[:]
        regex_assigns = {}
        while to_assing:
            regex_tmp = {name: min(regexes[name], key=lambda x: regex_score[x]) for name in to_assing}
            _, worst_regex = max(regex_tmp.items(), key=lambda x: regex_score[x[1]])
            for name in to_assing[:]:
                if worst_regex in regexes[name]:
                    regex_assigns[name] = worst_regex
                    to_assing.remove(name)
        # Uniquefy the regexes to avoid repetition
        return set(regex_assigns.values())
    
    # Validates if the regex created will highlight any scarabs that should be kept
    def validate_regex(self, orig_regex: str) -> bool:
        # Clean regex str to use with python's re
        regex = orig_regex.replace('"', '')
        highlight_keep_scarabs = regex[0] == '!'
        regex = regex[1:] if highlight_keep_scarabs else regex

        # Remove all ^ and $ from scarab names.
        keep_pre = [name.replace('^','').replace('$','') for name in self.keep]
        PDEBUG(keep_pre)
        # Filter list to see if there are any scarabs that should be kept that are being highlighted erroneously.
        keep = [name for name in keep_pre if re.search(regex, name)]
        PDEBUG(keep)

        DEBUG("Both lists should be the same length if original regex starts with '!' otherwise, the final list's length should be 0.")
        DEBUG(f"Len1: {RED}{len(keep_pre)}{END}, len2: {RED}{len(keep)}{END}. Has negation?: {RED}{highlight_keep_scarabs}{END}")
        DEBUG(f"Original regex:\n{NFORCED}{orig_regex}{END}")
        # returns True if there are no valuable scarabs being falsely appointed to be removed 
        return len(keep) == len(keep_pre) if highlight_keep_scarabs else len(keep) == 0

    # Create the full regex string based on the individual regexes
    # "!^(r1|(r21|scarab (r221|of (r222))).*)|.*(r31|scarab (r321|of (r322))|r33 scarab|r34 scarab ).*|.*(r41|(r42) scarab)$"
    def __format_scarab_regex(self, regs: Set[str], negate: bool) -> str:
        regexes = list(regs)
        PDEBUG(sorted(regexes))
        # Regexes that match a full line
        r1 = [item for item in regexes if item.startswith("^") and item.endswith("$")]
        for item in r1: regexes.remove(item)
        r1 = [item.strip("^$") for item in r1]
        DEBUG(f"r1={r1}")
        # Regexes that match the start of a line but don't start with "scarab "
        r21 = [item for item in regexes if item.startswith("^") and not item.strip("^").startswith("scarab ")]
        for item in r21: regexes.remove(item)
        r21 = [item.strip("^") for item in r21]
        DEBUG(f"r21={r21}")
        # Regexes that match the start of a line and start with "scarab " but don't start with "scarab of "
        r221 = [item for item in regexes if item.startswith("^") and item.strip("^").startswith("scarab ") and not item.strip("^").startswith("scarab of ")]
        for item in r221: regexes.remove(item)
        r221 = [item.strip("^").replace("scarab ", "") for item in r221]
        DEBUG(f"r221={r221}")
        # Regexes that match the start of a line and start with "scarab of "
        r222 = [item for item in regexes if item.startswith("^") and item.strip("^").startswith("scarab of ")]
        for item in r222: regexes.remove(item)
        r222 = [item.strip("^").replace("scarab of ", "") for item in r222]
        DEBUG(f"r222={r222}")
        # Regexes that don't match the end of a line of the line and doesn't start with "scarab " neither ends with " scarab"
        r31 = [item for item in regexes if not item.endswith("$") and not item.startswith("scarab ") and not item.endswith(" scarab") and not item.endswith(" scarab ")]
        for item in r31: regexes.remove(item)
        DEBUG(f"r31={r31}")
        # Regexes that don't match the end of a line of the line and start with "scarab " but don't start with "scarab of "
        r321 = [item for item in regexes if not item.endswith("$") and item.startswith("scarab ") and not item.startswith("scarab of ")]
        for item in r321: regexes.remove(item)
        r321 = [item.replace("scarab ", "") for item in r321]
        DEBUG(f"r321={r321}")
        # Regexes that don't match the end of a line of the line and start with "scarab of "
        r322 = [item for item in regexes if not item.endswith("$") and item.startswith("scarab of ")]
        for item in r322: regexes.remove(item)
        r322 = [item.replace("scarab of ", "") for item in r322]
        DEBUG(f"r322={r322}")
        # Regexes that don't match the end of a line of the line and ends with " scarab"
        r33 = [item for item in regexes if not item.endswith("$") and item.endswith(" scarab")]
        for item in r33: regexes.remove(item)
        r33 = [item.replace(" scarab", "") for item in r33]
        DEBUG(f"r33={r33}")
        # Regexes that don't match the end of a line of the line and ends with " scarab "
        r34 = [item for item in regexes if not item.endswith("$") and item.endswith(" scarab ")]
        for item in r34: regexes.remove(item)
        r34 = [item.replace(" scarab ", "") for item in r34]
        DEBUG(f"r34={r34}")
        # Regexes that match the end of a line of the line and doesn't ends with " scarab"
        r41 = [item for item in regexes if item.endswith("$") and not item.strip("$").endswith(" scarab")]
        for item in r41: regexes.remove(item)
        DEBUG(f"r41={r41}")
        # Regexes that match the end of a line of the line and ends with " scarab"
        r42 = [item for item in regexes if item.endswith("$") and item.strip("$").endswith(" scarab")]
        for item in r42: regexes.remove(item)
        r42 = [item.strip("$").replace(" scarab", "") for item in r42]
        DEBUG(f"r42={r42}")
        if regexes: raise Exception(f"Regexes list not empty at the end of group parsing '{regexes}'")
        has_start = len(r1 + r21 + r221 + r222) > 0
        has_end = len(r41 + r42) > 0
        regex_r1 = f"{'|'.join(r1)}"
        DEBUG("regex_r1:")
        DEBUG(regex_r1)
        regex_r21 = f"{'|'.join(r21)}"
        regex_r22 = f"scarab {'(' if r221 and len(r221 + r222) > 1 else ''}{'|'.join(r221)}{'|' if bool(r221) + bool(r222) > 1 else ''}of {'(' if len(r222) > 1 else ''}{'|'.join(r222)}{')' if len(r222) > 1 else ''}{')' if r221 and len(r221 + r222) > 1 else ''}" if r221 or r222 else ""
        regex_r2  = f"{regex_r21}{'|' if regex_r21 and regex_r22 else ''}{regex_r22}"
        DEBUG("regex_r2:")
        DEBUG(regex_r2)
        regex_r31 = f"{'|'.join(r31)}"
        regex_r32 = f"scarab {'(' if r321 and len(r321 + r322) > 1 else ''}{'|'.join(r321)}{'|' if r321 and r322 else ''}of {'(' if len(r322) > 1 else ''}{'|'.join(r322)}{')' if len(r322) > 1 else ''}{')' if r321 and  len(r321 + r322) > 1 else ''}" if r321 or r322 else ""
        regex_r33 = f"{'(' if len(r33) > 1 else ''}{'|'.join(r33)}{')' if len(r33) > 1 else ''} scarab" if r33 else ""
        regex_r34 = f"{'(' if len(r34) > 1 else ''}{'|'.join(r34)}{')' if len(r34) > 1 else ''} scarab " if r34 else ""
        regex_r3  = f"{'(' if bool(regex_r31) + bool(regex_r32) + bool(regex_r33) + bool(regex_r34) > 1 else ''}{regex_r31}{'|' if regex_r31 and (regex_r32 or regex_r33 or regex_r34) else ''}{regex_r32}{'|' if (regex_r31 or regex_r32) and (regex_r33 or regex_r34) else ''}{regex_r33}{'|' if (regex_r31 or regex_r32 or regex_r33) and regex_r34 else ''}{regex_r34}{')' if bool(regex_r31) + bool(regex_r32) + bool(regex_r33) + bool(regex_r34) > 1 else ''}"
        regex_r3  = re.sub(r"\|+", r"|", regex_r3)    
        DEBUG("regex_r3:")
        DEBUG(regex_r3)
        regex_r41 = f"{'|'.join(r41)}"
        regex_r42 = f"{'(' if len(r42) > 1 else ''}{'|'.join(r42)}{')' if len(r42) > 1 else ''} scarab" if r42 else ""
        regex_r4  = f"{regex_r41}{'|' if regex_r41 and regex_r42 else ''}{regex_r42}"
        DEBUG("regex_r4:")
        DEBUG(regex_r4)
        regex = f"{regex_r1}|{regex_r2}{'.*' if has_end and regex_r2 else ''}|{'.*' if has_start and regex_r3 else ''}{regex_r3}{'.*' if has_end and regex_r3 else ''}|{'.*' if has_start and regex_r4 else ''}{regex_r4}".strip("|")
        DEBUG("regex:")
        DEBUG(regex)
        regex = f"\"{'!' if negate else ''}{'^' if has_start else ''}{'(' if has_start or has_end else ''}{regex}{')' if has_start or has_end else ''}{'$' if has_end else ''}\""
        return regex

    def gen_scarab_regex(self, print_now: bool = True) -> str:
        self.get_prices()
        # Calculate the total regex lenght for highlighting the desired scarabs and highlighting the not of the undesired regexes
        normal_regexes  = self.__get_best_regexes(reverse_match=False, anchor_word="scarab")
        normal_regex    = self.__format_scarab_regex(normal_regexes, False)
        inverted_regexes= self.__get_best_regexes(reverse_match=True, anchor_word="scarab")
        inverted_regex  = self.__format_scarab_regex(inverted_regexes, True)
        
        # Select the regexes with the smallest total characters count
        regexes, negate = (normal_regexes, False) if len(normal_regex) <= len(inverted_regex) else (inverted_regexes, True)
        text_to_print = f"{REDB}Regex to Paste:{END}\n"
        text_to_return = ""
        # Print the regex in parts to abide by the POE regex character limit
        last_regexes = []
        for reg in regexes:
            test_reg = self.__format_scarab_regex(set(last_regexes + [reg]), negate)
            re.compile(test_reg)
            if len(test_reg) > self.__char_limit:
                regex = self.__format_scarab_regex(set(last_regexes), negate)
                re.compile(regex)
                if not self.validate_regex(regex):
                    text_to_print =  f"{REDBB}---->>> Some valuable scarabs are being marked to be vendored!! Aborting! <<<----\nContact devs to debug the issue!!{END}\n"
                    text_to_print += f"{NFORCED}broken regex: {regex}{END}\n"
                    return text_to_print
                text_to_print  += f"{REG}{regex}{END}\n"
                text_to_return += f"{regex}\n"
                last_regexes = [reg]
            else:
                last_regexes.append(reg)
        if last_regexes:
            regex = self.__format_scarab_regex(set(last_regexes), negate)
            re.compile(regex)
            if not self.validate_regex(regex):
                text_to_print =  f"{REDBB}---->>> Some valuable scarabs are being marked to be vendored!! Aborting! <<<----\nContact devs to debug the issue!!{END}\n"
                text_to_print += f"{NFORCED}broken regex: {regex}{END}\n"
                return text_to_print
            text_to_print += f"{REG}{regex}{END}\n"
            text_to_return += f"{regex}"
        text_to_print += f"{REDB}---------------------{END}"
        print(text_to_print) if print_now else None
        return text_to_return

    # Prints the regex to highlight cheapest N scarabs to vendor 
    def get_cheapest_n(self, N: int, print_now = True) -> str:
        self.get_prices()
        sorted_prices   = sorted(self.prices.items(), key=lambda x: x[1])
        to_vendor       = [name for name, price in sorted_prices[:N]]
        to_block        = [name for name, price in sorted_prices if name not in to_vendor]

        printvar = ''
        positive_reg = self.__format_scarab_regex(self.__get_best_regexes(_incl = to_vendor, _excl = to_block), False)
        if not self.validate_regex(positive_reg):
            printvar+="Regex might be broken, highlighting some wrong scarabs. Please double check.\n"
        
        printvar += f"{RED}cheapest {NFORCED}{N}{END} {RED}scarabs:{END}\n"
        printvar += f"{REG}{positive_reg}{END}\n"
        printvar += self.print_prices(print_now=print_now, _price_overload = {it: self.prices[it] for it in self.prices if it in to_vendor})
        print(printvar) if print_now else None
        return positive_reg

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Script to generate suitable regex strings to highlight vendorable scarabs.")
    ap.add_argument("-t", "--threshold", type=float, action="store", default=1, help="Cuttoff value for scarab price. Any below this will be highlighted")
    ap.add_argument("-l", "--limit", type=int, action="store", default=250, help="")
    ap.add_argument("-d", "--debug", action="store_true", help="Enables debug session", default=False)
    ap.add_argument("-p", "--print_prices", action="store_true", default=False, help="Prints latest price list.")
    ap.add_argument("-f", "--flip", action="store", type=int, help="Prints a regex with the cheapest N scarabs to put into Faustus' search bar to flip them.", default=None)
    ap.add_argument("-fk", "--force-keep", action="store", nargs="*", required=False, default=[], help="List of scarabs to force to be kept. Case insensitive, accepts regex.")
    args = ap.parse_args()
    # Print Debug info when DEBUG flag is active
    DEBUGGER = args.debug
    DEBUG("---------> Debug session active <----------")

    sr = scarab_regexer(force_keep=args.force_keep)
    
    # Constant values
    sr.update_value_threshold(args.threshold)
    sr.update_char_limit(args.limit)


    if args.print_prices:
        sr.print_prices()
    
    sr.gen_scarab_regex()

    if sr.forced:
        sr.print_forced()
    
    if args.flip:
        print("")
        sr.get_cheapest_n(N=args.flip)

