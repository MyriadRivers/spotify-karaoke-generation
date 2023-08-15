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
    
def get_musixmatch_data(musixmatch_json) -> (list[list[dict]], list[dict], list[int]):
    """
    Return a list of lines for the musixmatch lyric data, where each line is a list of words.
    A word is a dict: {"word": str, "startTime": int, "endTime": int}
    Also returns a list of all the musixmatch words not separated into lines.
    Finally, returns the indices of those words that correspond with the start of the lines. 
    """
    m_lyrics = []
    m_words = []
    m_line_indices = []

    m_word_index = 0

    for line in musixmatch_json["lyrics"]["lines"]:
        # Incinerate everything in paretheses, these are typically polyphonic vocal lines
        line["words"] = re.sub(r"\(.*?\)", "", line["words"])
        line["words"] = re.sub(r"\(+", "", line["words"])
        line["words"] = re.sub(r"\)+", "", line["words"])

        words = re.split(r"[\s-]+", line["words"])
        line_lyrics = []

        # Filter out empty words
        words = [w for w in words if w != ""]

        for i in range(len(words)):
            start_time = int(line["startTimeMs"]) if i == 0 else None
            end_time = None
            word_data = {"word": words[i], "startTime": start_time, "endTime": end_time}

            line_lyrics.append(word_data)

            if i == 0:
                m_line_indices.append(m_word_index)

            m_word_index += 1

        if len(line["words"]) != 0:
            m_lyrics.append(line_lyrics)
            m_words.extend(line_lyrics)

    #Append one more for easy slicing
    m_line_indices.append(len(m_words))

    return m_lyrics, m_words, m_line_indices

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

def get_lines(word_list, index_list):
    lines = []

    for i in range(len(index_list) - 1):
        start = index_list[i]
        end = index_list[i+1]
        line = word_list[start:end]

        # l = ""
        # for word in line:
        #     l += word["word"] + " "
        # print(l)

        lines.append(line)

    return lines

def get_word_match_indices(m_lines, w_lines, m_words, w_words) -> (list[int], list[int]):
    line_count = len(m_lines)
    m_word_i = 0
    w_word_i = 0
    
    m_words_matches = []
    w_words_matches = []

    for line_i in range(line_count):

        m_line_len = len(m_lines[line_i])
        w_line_len = len(w_lines[line_i])

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
        # print()
        # debug_arr = []
        # for j in range(len(match_arr[0])):
        #     debug_line = []
        #     for i, l in enumerate(match_arr):
        #         debug_line.append([l[j]["matches"], (l[j]["m_i"], l[j]["w_i"]), l[j]["syl_dif"]])
        #     print(debug_line)
        #     debug_arr.append(debug_line)

        # Trace backwards to get the optimal matches
        matches_m = []
        matches_w = []

        trace_m_i = len(m_lines[line_i])
        trace_w_i = len(w_lines[line_i])
        trace_curr = match_arr[trace_m_i][trace_w_i]

        while (trace_curr["m_i"] != None or trace_curr["w_i"] != None) and trace_m_i >= 0 and trace_w_i >= 0:
            trace_prev_m = match_arr[trace_m_i - 1][trace_w_i]
            trace_prev_w = match_arr[trace_m_i][trace_w_i - 1]

            if match(m_words[trace_m_i + m_word_i - m_line_len - 1]["word"], \
                    w_words[trace_w_i + w_word_i - w_line_len - 1]["word"]):
                
                matches = match_arr[trace_m_i][trace_w_i]["matches"]
                syl_dif = match_arr[trace_m_i][trace_w_i]["syl_dif"]
                
                if matches == trace_prev_m["matches"] and syl_dif >= trace_prev_m["syl_dif"]:
                    trace_m_i -= 1
                elif matches == trace_prev_w["matches"] and syl_dif >= trace_prev_w["syl_dif"]:
                    trace_w_i -= 1
                else:
                    matches_m.insert(0, trace_curr["m_i"])
                    matches_w.insert(0, trace_curr["w_i"])
                    trace_m_i -= 1
                    trace_w_i -= 1
            else:
                if trace_prev_m["matches"] > trace_prev_w["matches"]:
                    trace_m_i -= 1
                elif trace_prev_m["matches"] < trace_prev_w["matches"]:
                    trace_w_i -= 1
                else:
                    if (trace_prev_m["m_i"] != None and trace_prev_w["m_i"] == None) or trace_prev_m["syl_dif"] < trace_prev_w["syl_dif"]:
                        trace_m_i -= 1
                    elif (trace_prev_w["m_i"] != None and trace_prev_m["m_i"] == None) or trace_prev_m["syl_dif"] >= trace_prev_w["syl_dif"]:
                        trace_w_i -= 1

            trace_curr = match_arr[trace_m_i][trace_w_i]
        
        # Match the start of whisper line to the start of musixmatch line if neither word is already matched
        if m_word_i - m_line_len not in matches_m and w_word_i - w_line_len not in matches_w:

            # Alter the whisper words to break apart the first word of the line so that remaining syllables can still be matched
            m_fir = musixmatch_words[m_word_i - m_line_len]
            w_fir = whisper_words[w_word_i - w_line_len]

            m_fir_syl = count_syllables(m_fir["word"])
            w_fir_syl = count_syllables(w_fir["word"])

            fir_syl_dif = m_fir_syl - w_fir_syl

            # CASE 1: Whisper's first word has too many syllables
            if fir_syl_dif < 0:
                extra_syl = abs(fir_syl_dif)

                # Add a new padword from the remains of the first whisper word
                pad_start = (((w_fir["endTime"] - w_fir["startTime"]) / w_fir_syl) * (w_fir_syl - extra_syl)) + w_fir["startTime"]
                pad_word = {"word": "pad" * extra_syl, "startTime": pad_start, "endTime": w_fir["endTime"]}
                whisper_words.insert(w_word_i - w_line_len + 1, pad_word)
                
                # Change end time of first word since we cut it
                whisper_words[w_word_i - w_line_len]["endTime"] = pad_start

                # We inserted a new pad word, so we need to adjust all the match indices by 1
                matches_w = [(w + 1) for w in matches_w]

            # CASE 2: Musixmatch's first word has too many syllables
            elif fir_syl_dif > 0:
                syl_i = 0
                word_i = 0
                w_indices_deleted = []

                # Mark words that should be matched to the first musixmatch word for deletion

                while syl_i < fir_syl_dif:
                    w_word_index =  w_word_i - w_line_len + word_i + 1
                    # Start counting from one after the first word
                    syl = count_syllables(whisper_words[w_word_index]["word"])

                    # If the word we're about to delete has extra syllables that go beyond the first musixmatch word's
                    # We split it to only delete the ones matched to the musixmatch word
                    if (syl_i + syl) > fir_syl_dif:
                        extra_syl = (syl_i + syl) - fir_syl_dif
                        in_syl = syl - extra_syl

                        break_word = whisper_words[w_word_index]

                        extra_start = (((break_word["endTime"] - break_word["startTime"]) / syl) * in_syl) + break_word["startTime"]
                        extra_word = {"word": "pad" * extra_syl, "startTime": extra_start, "endTime": break_word["endTime"]}
                        
                        # Adjust the first word to end where the pad begins since we deleted a bunch between them
                        whisper_words[w_word_i - w_line_len]["endTime"] = extra_start

                        whisper_words.insert(w_word_index + 1, extra_word)
                        matches_w = [(w + 1) for w in matches_w]

                    # This should only ever have one element, as only one word can be split on the musixmatch syllable border
                    w_indices_deleted.append(w_word_index)
                    
                    syl_i += syl
                    word_i += 1
                
                # Delete them in reverse order to not throw off the indices
                for index in sorted(w_indices_deleted, reverse=True):
                    del whisper_words[index]

                # Adjust matches by the number of words we deleted
                matches_w = [(w - len(w_indices_deleted)) for w in matches_w]

            matches_m.insert(0, m_word_i - m_line_len)
            matches_w.insert(0, w_word_i - w_line_len)

        m_words_matches.extend(matches_m)
        w_words_matches.extend(matches_w)

    return m_words_matches, w_words_matches

"""Public Method"""
def get_karaoke_lines(m_path: str, w_path: str) -> list[list[dict]]:
    """Time stamp the start and end of every word in a song, grouped by lines, for karaoke playback.

    Args:
        m_path: file path of the Musixmatch json data file of the lyrics, such as that generated by syrics.
        w_path: file path of the Whisper json data file of the audio transcription.

    Returns:
        List of lines corresponding to the lines of the song from Musixmatch, where each line is a list of words.
        A word is a dictionary {"word": <word>, "startTime": <start time of word in ms>, "endTime": <end time of word in ms>}.
    """
    def get_word_match_indices(m_lines, w_lines, m_words, w_words) -> (list[int], list[int]):
        line_count = len(m_lines)
        m_word_i = 0
        w_word_i = 0
        
        m_words_matches = []
        w_words_matches = []

        for line_i in range(line_count):

            m_line_len = len(m_lines[line_i])
            w_line_len = len(w_lines[line_i])

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
            # print()
            # debug_arr = []
            # for j in range(len(match_arr[0])):
            #     debug_line = []
            #     for i, l in enumerate(match_arr):
            #         debug_line.append([l[j]["matches"], (l[j]["m_i"], l[j]["w_i"]), l[j]["syl_dif"]])
            #     print(debug_line)
            #     debug_arr.append(debug_line)

            # Trace backwards to get the optimal matches
            matches_m = []
            matches_w = []

            trace_m_i = len(m_lines[line_i])
            trace_w_i = len(w_lines[line_i])
            trace_curr = match_arr[trace_m_i][trace_w_i]

            while (trace_curr["m_i"] != None or trace_curr["w_i"] != None) and trace_m_i >= 0 and trace_w_i >= 0:
                trace_prev_m = match_arr[trace_m_i - 1][trace_w_i]
                trace_prev_w = match_arr[trace_m_i][trace_w_i - 1]

                if match(m_words[trace_m_i + m_word_i - m_line_len - 1]["word"], \
                        w_words[trace_w_i + w_word_i - w_line_len - 1]["word"]):
                    
                    matches = match_arr[trace_m_i][trace_w_i]["matches"]
                    syl_dif = match_arr[trace_m_i][trace_w_i]["syl_dif"]
                    
                    if matches == trace_prev_m["matches"] and syl_dif >= trace_prev_m["syl_dif"]:
                        trace_m_i -= 1
                    elif matches == trace_prev_w["matches"] and syl_dif >= trace_prev_w["syl_dif"]:
                        trace_w_i -= 1
                    else:
                        matches_m.insert(0, trace_curr["m_i"])
                        matches_w.insert(0, trace_curr["w_i"])
                        trace_m_i -= 1
                        trace_w_i -= 1
                else:
                    if trace_prev_m["matches"] > trace_prev_w["matches"]:
                        trace_m_i -= 1
                    elif trace_prev_m["matches"] < trace_prev_w["matches"]:
                        trace_w_i -= 1
                    else:
                        if (trace_prev_m["m_i"] != None and trace_prev_w["m_i"] == None) or trace_prev_m["syl_dif"] < trace_prev_w["syl_dif"]:
                            trace_m_i -= 1
                        elif (trace_prev_w["m_i"] != None and trace_prev_m["m_i"] == None) or trace_prev_m["syl_dif"] >= trace_prev_w["syl_dif"]:
                            trace_w_i -= 1

                trace_curr = match_arr[trace_m_i][trace_w_i]
            
            # Match the start of whisper line to the start of musixmatch line if neither word is already matched
            if m_word_i - m_line_len not in matches_m and w_word_i - w_line_len not in matches_w:

                # Alter the whisper words to break apart the first word of the line so that remaining syllables can still be matched
                m_fir = musixmatch_words[m_word_i - m_line_len]
                w_fir = whisper_words[w_word_i - w_line_len]

                m_fir_syl = count_syllables(m_fir["word"])
                w_fir_syl = count_syllables(w_fir["word"])

                fir_syl_dif = m_fir_syl - w_fir_syl

                # CASE 1: Whisper's first word has too many syllables
                if fir_syl_dif < 0:
                    extra_syl = abs(fir_syl_dif)

                    # Add a new padword from the remains of the first whisper word
                    pad_start = (((w_fir["endTime"] - w_fir["startTime"]) / w_fir_syl) * (w_fir_syl - extra_syl)) + w_fir["startTime"]
                    pad_word = {"word": "pad" * extra_syl, "startTime": pad_start, "endTime": w_fir["endTime"]}
                    whisper_words.insert(w_word_i - w_line_len + 1, pad_word)
                    
                    # Change end time of first word since we cut it
                    whisper_words[w_word_i - w_line_len]["endTime"] = pad_start

                    # We inserted a new pad word, so we need to adjust all the match indices by 1
                    matches_w = [(w + 1) for w in matches_w]

                # CASE 2: Musixmatch's first word has too many syllables
                elif fir_syl_dif > 0:
                    syl_i = 0
                    word_i = 0
                    w_indices_deleted = []

                    # Mark words that should be matched to the first musixmatch word for deletion

                    while syl_i < fir_syl_dif:
                        w_word_index =  w_word_i - w_line_len + word_i + 1
                        # Start counting from one after the first word
                        syl = count_syllables(whisper_words[w_word_index]["word"])

                        # If the word we're about to delete has extra syllables that go beyond the first musixmatch word's
                        # We split it to only delete the ones matched to the musixmatch word
                        if (syl_i + syl) > fir_syl_dif:
                            extra_syl = (syl_i + syl) - fir_syl_dif
                            in_syl = syl - extra_syl

                            break_word = whisper_words[w_word_index]

                            extra_start = (((break_word["endTime"] - break_word["startTime"]) / syl) * in_syl) + break_word["startTime"]
                            extra_word = {"word": "pad" * extra_syl, "startTime": extra_start, "endTime": break_word["endTime"]}
                            
                            # Adjust the first word to end where the pad begins since we deleted a bunch between them
                            whisper_words[w_word_i - w_line_len]["endTime"] = extra_start

                            whisper_words.insert(w_word_index + 1, extra_word)
                            matches_w = [(w + 1) for w in matches_w]

                        # This should only ever have one element, as only one word can be split on the musixmatch syllable border
                        w_indices_deleted.append(w_word_index)
                        
                        syl_i += syl
                        word_i += 1
                    
                    # Delete them in reverse order to not throw off the indices
                    for index in sorted(w_indices_deleted, reverse=True):
                        del whisper_words[index]

                    # Adjust matches by the number of words we deleted
                    matches_w = [(w - len(w_indices_deleted)) for w in matches_w]

                matches_m.insert(0, m_word_i - m_line_len)
                matches_w.insert(0, w_word_i - w_line_len)

            m_words_matches.extend(matches_m)
            w_words_matches.extend(matches_w)

        return m_words_matches, w_words_matches

    # GET LYRICS FROM JSON FILES
    with open(m_path, "r") as m:
        mjson = m.read().rstrip()

    with open(w_path, "r") as w:
        wjson = w.read().rstrip()

    musixmatch_data = json.loads(mjson)
    whisper_data = json.loads(wjson)

    musixmatch_lines, musixmatch_words, musixmatch_line_indices = get_musixmatch_data(musixmatch_data)
    whisper_words = get_whisper_words(whisper_data)
    whisper_line_indices = get_whisper_line_breaks(whisper_words, musixmatch_lines)
    whisper_lines = get_lines(whisper_words, whisper_line_indices)

    # Match whisper words to musixmatch words similar to greatest common subsequence

    m_matches, w_matches = get_word_match_indices(musixmatch_lines, whisper_lines, musixmatch_words, whisper_words)

    m_gap_indices = []
    w_gap_indices = []

    prev_i = 0
    # + 1 in case the last match happens before the end of the lyrics, so we can check gap after the last match
    for i in range(len(m_matches) + 1):
        # Assign time stamps for the perfectly matched words
        if i < len(m_matches):
            musixmatch_words[m_matches[i]]["startTime"] = whisper_words[w_matches[i]]["startTime"]
            musixmatch_words[m_matches[i]]["endTime"] = whisper_words[w_matches[i]]["endTime"]

        m_gap_indices = [x for x in range(m_matches[prev_i] + 1, m_matches[i] if i < len(m_matches) else len(musixmatch_words))]
        w_gap_indices = [x for x in range(w_matches[prev_i] + 1, w_matches[i] if i < len(w_matches) else len(whisper_words))]

        # Assign time stamps for the gap words
        if len(m_gap_indices) != 0:

            m_syl = 0
            w_syl = 0

            m_syl_total = 0
            m_syl_indices = []

            w_syl_total = 0
            w_syl_indices = []

            for m_gap_i in m_gap_indices:
                m_syl_indices.append(m_syl_total)
                m_syl_total += count_syllables(musixmatch_words[m_gap_i]["word"])

            for w_gap_i in w_gap_indices:
                w_syl_indices.append(w_syl_total)
                w_syl_total += count_syllables(whisper_words[w_gap_i]["word"])

            # Generate a timestamp for every syllable possible in gap space

            w_syl_timestamps = []

            m_gaps = []
            w_gaps = []
            for index in m_gap_indices:
                m_gaps.append(musixmatch_words[index])
            for index in w_gap_indices:
                w_gaps.append(whisper_words[index])

            # Generate time stamps for whisper by breaking words up into syllables and linearly interpolating between words by syllables
            for w_word in w_gaps:
                w_word_syl_count = count_syllables(w_word["word"])

                for syl_i in range(w_word_syl_count):
                    syl_start_time = (((w_word["endTime"] - w_word["startTime"]) / w_word_syl_count) * syl_i) + w_word["startTime"]
                    syl_end_time = (((w_word["endTime"] - w_word["startTime"]) / w_word_syl_count) * (syl_i + 1)) + w_word["startTime"]

                    w_syl_timestamps.append({"startTime": syl_start_time, "endTime": syl_end_time})

            # Some of the musixmatch syllables don't have a corresponding syllable in whisper
            if (m_syl_total > w_syl_total):
                prev_border_i = w_matches[prev_i] + len(w_gap_indices)
                next_border_i = w_matches[i] if i < len(w_matches) else len(whisper_words)

                # If the first musixmatch words are unmatched, we guess where the start the start of the line is
                # by taking the first detected whisper word - the length of the first word * the number of missing words
                # This cannot be earlier that 0, the start of the song
                w_first_syl = count_syllables(whisper_words[0]["word"])
                w_last_syl = count_syllables(whisper_words[-1]["word"])
                w_first_syl_length = (whisper_words[0]["endTime"] - whisper_words[0]["startTime"]) / w_first_syl
                w_last_syl_length = (whisper_words[-1]["endTime"] - whisper_words[-1]["startTime"]) / w_last_syl

                prev_border = whisper_words[prev_border_i]["endTime"] if not (prev_border_i == 0 and next_border_i == 0) \
                    else max(min(musixmatch_words[0]["startTime"], 
                                whisper_words[0]["startTime"] - ((m_syl_total - w_syl_total) * w_first_syl_length)), 0)
                
                # If the last musixmatch words are unmatched, we calculate the end border in a similar way
                # Should also make it not go past the end of the song
                next_border = whisper_words[next_border_i]["startTime"] if next_border_i < len(whisper_words) \
                    else max(whisper_words[-1]["endTime"] + w_last_syl_length * (m_syl_total - w_syl_total), 
                            int(musixmatch_data["lyrics"]["lines"][-1]["startTimeMs"]))
                
                # Generate extra timestamps for syllables that go beyond how many words whisper has
                for extra_i in range(m_syl_total - w_syl_total):

                    syl_start_time = (((next_border - prev_border) / (m_syl_total - w_syl_total)) * extra_i) + prev_border
                    syl_end_time = (((next_border - prev_border) / (m_syl_total - w_syl_total)) * (extra_i + 1)) + prev_border

                    w_syl_timestamps.append({"startTime": syl_start_time, "endTime": syl_end_time})

            # Assign timestamps to the unmatched musixmatch words from whisperwords by syllable count
            for syl_i, gap_i in enumerate(m_gap_indices):
                musixmatch_words[gap_i]["startTime"] = w_syl_timestamps[syl_i]["startTime"]
                musixmatch_words[gap_i]["endTime"] = w_syl_timestamps[syl_i]["endTime"]

        prev_i = i

    # Now, break the words back into lines
    karaoke_lines = get_lines(musixmatch_words, musixmatch_line_indices)

    # Check the final lines
    
    # for k_line in karaoke_lines:
    #     k_line_string = ""

    #     for k_word in k_line:
    #         k_line_string += k_word["word"] + " "

    #         if (k_word["startTime"] == None or k_word["startTime"] == None):
    #             print("Dropped a word")

    #     print(k_line_string)

    return karaoke_lines