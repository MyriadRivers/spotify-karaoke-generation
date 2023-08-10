import json
import re
from syllabify.syllable3 import generate

def match(word1: str, word2: str) -> bool:
    """
    How to determine word equivalence. Right now they have to be the same, but later maybe consider pronunciation.
    """
    word1 = re.sub(r"[^\w']+", "", word1).lower()
    word2 = re.sub(r"[^\w']+", "", word2).lower()

    # if generate(word1.rstrip()) == None or generate(word2.rstrip()) == None:
    #     return False

    # syllables1 = list(generate(word1.rstrip()))[0]
    # syllables2 = list(generate(word2.rstrip()))[0]
    
    # return len(syllables1) == 1 and len(syllables2) == 1 and syllables1[0].get_nucleus() == syllables2[0].get_nucleus()
    
    # gerunds that end in " ing " versus " in' " are the same word
    if word1.endswith("ing") and word2.endswith("in'"):
        word1 = word1[:-1] + "'"
    if word1.endswith("in'") and word2.endswith("ing"):
        word2 = word2[:-1] + "'"

    return word1 == word2
        

def guess_syllables(word):
    """
    Fall back function for estimating number of syllables in case word is not found in CMU dictionary.
    """
    #referred from stackoverflow.com/questions/14541303/count-the-number-of-syllables-in-a-word
    count = 0
    vowels = 'aeiouy'
    word = word.lower()
    if word[0] in vowels:
        count +=1
    for index in range(1,len(word)):
        if word[index] in vowels and word[index-1] not in vowels:
            count +=1
    if word.endswith('e'):
        count -= 1
    if word.endswith('le'):
        count += 1
    if count == 0:
        count += 1
    return count

def count_syllables(word: str) -> int:
    """
    Returns number of syllables in the word, referencing the CMU dictionary, otherwise estimates.
    """
    word = re.sub(r"[^\w']+", "", word).lower().rstrip()
    if len(word) == 0:
        return 0
    try:
        syl = generate(word)
        return len(list(syl)[0])
    except TypeError:
        return guess_syllables(word)
    
def get_musixmatch_lines_and_words(musixmatch_json) -> (list[list[dict]], list[dict]):
    """
    Return a list of lines for the musixmatch lyric data, where each line is a list of words.
    A word is a dict: {"word": str, "startTime": int, "endTime": int}
    """
    m_lyrics = []
    m_words = []

    for line in musixmatch_json["lyrics"]["lines"]:
        # Incinerate everything in paretheses, these are typically polyphonic vocal lines
        line["words"] = re.sub(r"\(.*?\)", "", line["words"])
        line["words"] = re.sub(r"\(+", "", line["words"])
        line["words"] = re.sub(r"\)+", "", line["words"])

        words = re.split(r"[\s-]+", line["words"])
        line_lyrics = []

        for i in range(len(words)):
            start_time = int(line["startTimeMs"]) if i == 0 else None
            end_time = None
            word_data = {"word": words[i], "startTime": start_time, "endTime": end_time}

            line_lyrics.append(word_data)

        if len(line["words"]) != 0:
            m_lyrics.append(line_lyrics)
            m_words.extend(line_lyrics)

    return m_lyrics, m_words

def get_whisper_words(whisper_json) -> list[dict]:
    """
    Return a list of all the words taken from the whisper transcription.
    A word is a dict: {"word": str, "startTime": int, "endTime": int}
    """

    words = []

    # First get all the words from whisper
    for line in whisper_json:
        line_words = [{"word": word["word"], "startTime": int(word["start"] * 1000), "endTime": int(word["end"] * 1000)} for word in line["words"] if "start" in word]
        
        l = ""
        for word in line_words:
            l += word["word"] + " "
            words.append(word)
        # print(l)

    return words

def get_whisper_line_breaks(w_words, m_lines, MAX_TIME_GAP_MS: int = 500):
    """
    Get indices of all whisper words that correspond to the start of a musixmatch line. 
    Plus an index at the end of the song marking where the whisper words terminate.
    """
    line_word_breaks = []

    for m_line in m_lines:

        # Time difference between whisper word timestamp and musixmatch line timestamp
        min_time_dif = abs(w_words[0]["startTime"] - m_line[0]["startTime"])
        prev_time_dif = abs(w_words[0]["startTime"] - m_line[0]["startTime"])

        # booleans representing if the lyrics match
        prev_match = match(w_words[0]["word"], m_line[0]["word"])
        curr_match = match(w_words[0]["word"], m_line[0]["word"])
        
        word_index = 0

        for w_index, w_word in enumerate(w_words):
            time_dif = abs(w_word["startTime"] - m_line[0]["startTime"])

            curr_match = match(w_word["word"], m_line[0]["word"])

            # Match w word to start of m line if its the minimum time, 
            # - OR its a perfect word match even if its not the minimum, but only if previous is not also perfect
            # - But don't do minimum time if you'll be overriding a previous perfect match and you aren't a perfect match
            if (time_dif < min_time_dif or (curr_match and not prev_match and time_dif < MAX_TIME_GAP_MS)) and not (prev_match and not curr_match and prev_time_dif < MAX_TIME_GAP_MS):
                min_time_dif = time_dif
                word_index = w_index

            prev_match = curr_match
            prev_time_dif = time_dif
        
        line_word_breaks.append(word_index)

    # Append one more index so we can slice easily
    line_word_breaks.append(len(w_words))

    return line_word_breaks

def get_whisper_lines(w_words, m_lines):
    line_word_breaks = get_whisper_line_breaks(w_words, m_lines)
    w_lyrics = []

    for i in range(len(line_word_breaks) - 1):
        start = line_word_breaks[i]
        end = line_word_breaks[i+1]
        line = w_words[start:end]

        l = ""
        for word in line:
            l += word["word"] + " "
        print(l)

        w_lyrics.append(line)

    return w_lyrics

def get_word_match_indices(m_lines, w_lines, m_words, w_words) -> (list[int], list[int]):
    line_count = len(m_lines)
    m_word_i = 0
    w_word_i = 0
    
    m_words_matches = []
    w_words_matches = []

    for line_i in range(line_count):

        m_line_len = len(m_lines[line_i])
        w_line_len = len(w_lines[line_i])

        wordos_m = [i["word"] for i in m_lines[line_i]]
        wordos_w = [i["word"] for i in w_lines[line_i]]
        print()
        print(wordos_m)
        print(wordos_w)

        # Initialize the array with leading row and column of zeroes
        default_match = {"matches": 0, "m_i": None, "w_i": None, "syl_dif": 999}
        match_arr = [[default_match] * (w_line_len + 1)] + [[default_match] + [None] * w_line_len for _ in range(m_line_len)]
        
        m_syl_i = 0   

        for m_i, m_word in enumerate(m_lines[line_i], 1):
            m_syl = count_syllables(m_word["word"])
            w_syl_i = 0 

            for w_i, w_word in enumerate(w_lines[line_i], 1):
                w_syl = count_syllables(w_word["word"])

                prev_m = match_arr[m_i - 1][w_i]
                prev_w = match_arr[m_i][w_i - 1]

                if not match(m_word["word"], w_word["word"]):
                    if prev_m["matches"] > prev_w["matches"]:
                        match_arr[m_i][w_i] = prev_m
                    elif prev_m["matches"] < prev_w["matches"]:
                        match_arr[m_i][w_i] = prev_w
                    else:
                        match_arr[m_i][w_i] = prev_m if prev_m["syl_dif"] < prev_w["syl_dif"] else prev_w
                else:
                    matches = match_arr[m_i - 1][w_i - 1]["matches"] + 1
                    syl_dif = abs(m_syl_i - w_syl_i)

                    if matches == prev_m["matches"] and syl_dif >= prev_m["syl_dif"]:
                        match_arr[m_i][w_i] = prev_m
                    elif matches == prev_w["matches"] and syl_dif >= prev_w["syl_dif"]:
                        match_arr[m_i][w_i] = prev_w
                    else:
                        # set to m_i - 1 and w_i - 1 to account for the row/column indices starting at 1
                        total_m_i = m_word_i
                        total_w_i = w_i - 1 + w_word_i
                        match_arr[m_i][w_i] = {"matches": matches, "m_i": total_m_i, "w_i": total_w_i, "syl_dif": syl_dif}
    
                w_syl_i += w_syl

            m_syl_i += m_syl
            m_word_i += 1

        w_word_i += w_line_len

        # Debug the matches array
        print()
        debug_arr = []
        for j in range(len(match_arr[0])):
            debug_line = []
            for i, l in enumerate(match_arr):
                debug_line.append([l[j]["matches"], (l[j]["m_i"], l[j]["w_i"]), l[j]["syl_dif"]])
            print(debug_line)
            debug_arr.append(debug_line)

        # Trace backwards to get the optimal matches
        matches_m = []
        matches_w = []

        trace_m_i = len(m_lines[line_i])
        trace_w_i = len(w_lines[line_i])
        trace_curr = match_arr[trace_m_i][trace_w_i]

        while (trace_curr["m_i"] != None or trace_curr["w_i"] != None) and trace_m_i >= 0 and trace_w_i >= 0:
            trace_prev_m = match_arr[trace_m_i - 1][trace_w_i]
            trace_prev_w = match_arr[trace_m_i][trace_w_i - 1]

            print()
            print("comparing " + m_words[match_arr[trace_m_i][trace_w_i]["m_i"]]["word"] + " and " + w_words[match_arr[trace_m_i][trace_w_i]["w_i"]]["word"])
            print("at " + str(trace_m_i) + ", " + str(trace_w_i))
            print()

            if match(m_words[trace_m_i + m_word_i - m_line_len - 1]["word"], \
                    w_words[trace_w_i + w_word_i - w_line_len - 1]["word"]):
                
                matches = match_arr[trace_m_i][trace_w_i]["matches"]
                syl_dif = match_arr[trace_m_i][trace_w_i]["syl_dif"]
                
                if matches == trace_prev_m["matches"] and syl_dif >= trace_prev_m["syl_dif"]:
                    trace_m_i -= 1
                    print("match, go back M")
                elif matches == trace_prev_w["matches"] and syl_dif >= trace_prev_w["syl_dif"]:
                    trace_w_i -= 1
                    print("match, go back W")
                else:
                    matches_m.insert(0, trace_curr["m_i"])
                    matches_w.insert(0, trace_curr["w_i"])
                    trace_m_i -= 1
                    trace_w_i -= 1
                    print("match, go back BOTH")
            else:
                if trace_prev_m["matches"] > trace_prev_w["matches"]:
                    trace_m_i -= 1
                    print("no match, go back M")
                elif trace_prev_m["matches"] < trace_prev_w["matches"]:
                    trace_w_i -= 1
                    print("no match, go back W")
                else:
                    if (trace_prev_m["m_i"] != None and trace_prev_w["m_i"] == None) or trace_prev_m["syl_dif"] < trace_prev_w["syl_dif"]:
                        trace_m_i -= 1
                        print("no match, go back M by syllables")
                    elif (trace_prev_w["m_i"] != None and trace_prev_m["m_i"] == None) or trace_prev_m["syl_dif"] >= trace_prev_w["syl_dif"]:
                        trace_w_i -= 1
                        print("no match, go back W by syllables")

            trace_curr = match_arr[trace_m_i][trace_w_i]
        
        # Match the start of whisper line to the start of musixmatch line if neither word is already matched
        if m_word_i - m_line_len not in matches_m and w_word_i - w_line_len not in matches_w:
            matches_m.insert(0, m_word_i - m_line_len)
            matches_w.insert(0, w_word_i - w_line_len)

        m_words_matches.extend(matches_m)
        w_words_matches.extend(matches_w)

        print()
        print(matches_m)
        print(matches_w)

    return m_words_matches, w_words_matches

# GET LYRICS FROM JSON FILES
m_path = "call-m.json"
w_path = "call-w.json"

with open(m_path, "r") as m:
    mjson = m.read().rstrip()

with open(w_path, "r") as w:
    wjson = w.read().rstrip()

musixmatch_data = json.loads(mjson)
whisper_data = json.loads(wjson)

musixmatch_lines, musixmatch_words = get_musixmatch_lines_and_words(musixmatch_data)
whisper_words = get_whisper_words(whisper_data)
whisper_lines = get_whisper_lines(whisper_words, musixmatch_lines)

# Match whisper words to musixmatch words similar to greatest common subsequence

m_matches, w_matches = get_word_match_indices(musixmatch_lines, whisper_lines, musixmatch_words, whisper_words)

m_gap_words = []
w_gap_words = []

prev_i = 0
for i in range(len(m_matches)):
    # Assign time stamps for the perfectly matched words
    musixmatch_words[m_matches[i]] = whisper_words[w_matches[i]]

    m_gap_words = [x for x in range(m_matches[prev_i] + 1, m_matches[i])]
    w_gap_words = [x for x in range(w_matches[prev_i] + 1, w_matches[i])]

    # Assign time stamps for the gap words
    if len(m_gap_words) != 0:
        # # First assign all possible whisper timestamps
        # m_i = 0
        # m_syl = 0
        # w_syl = 0
        # for w_i in w_gap_words:
        #     if m_syl == w_syl:
        #         # musixmatch_words[m_gap_words[m_i]]["startTime"] = 
        #         pass

        m_gaps = []
        w_gaps = []
        for index in m_gap_words:
            m_gaps.append(musixmatch_words[index]["word"])
        for index in w_gap_words:
            w_gaps.append(whisper_words[index]["word"])

        print()
        print("m gap: " + str(m_gaps))
        print("w gap: " + str(w_gaps))
        print()

    prev_i = i

# print("\namogus\n")
# bobo = []
# for word in musixmatch_words:
#     bobo.append(word["word"])

# print(bobo)

# bobwo = []
# for word in whisper_words:
#     bobwo.append(word["word"])

# print(bobwo)

# gaga = []

# for line in musixmatch_lines:
#     print(line)


# print(musixmatch_words[406]["word"])
# print(whisper_words[398]["word"])
# print(musixmatch_words)

