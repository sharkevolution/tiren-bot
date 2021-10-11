import logging
import copy

FORMAT = '%(module)s - %(funcName)s -%(lineno)d - %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)

number_key = {'ent_one': 1, 'ent_two': 2, 'ent_three': 3, 'ent_four': 4,
              'ent_five': 5, 'ent_six': 6, 'ent_seven': 7, 'ent_eight': 8,
              'ent_nine': 9, 'ent_zero': 0, 'ent_colon': ':'}

valid_range = {'01': 1, '02': 1, '03': 1, '04': 1, '05': 1, '06': 1, '07': 1,
               '08': 1, '09': 1, '10': 1, '11': 1, '12': 1, '13': 1, '14': 1,
               '15': 1, '16': 1, '17': 1, '18': 1, '19': 1, '20': 1, '21': 1,
               '22': 1, '23': 1, '1': 1, '2': 1, '3': 1, '4': 1, '5': 1, '6': 1,
               '7': 1, '8': 1, '9': 9, '0': 0}


def check(ord, comb):
    tmp_list = copy.deepcopy(comb)

    if ':' in tmp_list:
        ind = tmp_list.index(':')
        left_side = tmp_list[:ind]
        right_side = tmp_list[ind + 1:]

        if right_side:
            if len(right_side) == 1:
                if str(number_key[ord]) in '0123456789':
                    right_side.append(str(number_key[ord]))
        else:
            if str(number_key[ord]) in '012345':
                right_side.append(str(number_key[ord]))

        tmp_list = left_side + [':'] + right_side

    else:
        left_side = []
        if len(tmp_list) == 1:
            if int(tmp_list[0]) == 2:
                if str(number_key[ord]) in '0123:':
                    left_side.append(str(number_key[ord]))
                    tmp_list += left_side
            else:
                if tmp_list[0] in '3456789':
                    pass
                else:
                    left_side.append(str(number_key[ord]))
                    tmp_list += left_side
            if not ':' == str(number_key[ord]):
                # left_side.append(':')
                tmp_list += ':'

            if len(tmp_list) == 2:
                tmp_list.insert(0, '0')
                new_comb = copy.deepcopy(tmp_list)
                tmp_list = check(ord, new_comb)

        elif len(tmp_list) == 2:
            left_side.append(':')
            tmp_list += left_side
        else:
            if str(number_key[ord]) in '0123456789':
                left_side.append(str(number_key[ord]))
            tmp_list += left_side

    comb = copy.deepcopy(tmp_list)

    return comb

