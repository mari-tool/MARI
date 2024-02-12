class TokenContainer():
    # initialize token object (can set values if needed)
    def __init__(self,t_name='no token selected',tot=0,u_lens=dict({}),pos=dict({})):
        self.text = t_name

        self.total_count = tot
        self.utterance_lengths = u_lens
        self.pos = pos
        self.ents = dict({})

        ################
        # from the paper "'Hello, [REDACTED]'"
        # the following can be made proportional to number of total occurrences
        # currently only counts capitalized words
        self.num_caps = 0
        self.num_middles = 0

        # from start of sentence
        self.num_beginnings = 0

        # related words in windows around word
        self.context_words = dict({})
        self.context_words_capital = dict({})
        self.context_words_mid_cap = dict({})

        #################

        # index of token in first utterance
        self.first_index = 0

        # set of dictionary words within X edit(s)
        self.edits_one =  None
        self.edits_two = None

        # num dictionary words within X edit(s)
        self.edit_count_one = 0
        self.edit_count_two = 0

        # set of idable words within X edit(s)
        self.lev_to_idables = None

        # num idable words within X edit(s)
        self.lev_to_id_count = 0

        #self.unique_flag = True
        # ^^ SEE self.indicators INSTEAD

        # related tokens are essentially the same word, for purposes of keeping track of
        # total count and such (only indices in the overall token list, for space)
        # problem is, this could still be enormous
        # list: Token
        self.related_tokens = []

        # related *types* as opposed to *tokens*:
        # like nicknames or synonyms
        # eg for Alexander, we have [Alex,Xander,Sasha,etc]
        # list: TokenContainerClass
        self.related_types = []

        # replacement values for this token (might be temporary?)  dict now for counting # types
        self.replacement_values = dict({})
        self.times_redacted = 0
        self.categories = set([])

        # dict of indicator variables for certain types of identifiable information
        self.indicators = dict({'dict_word':False,'potential_typo_unique':True})  # if we find a word that is not in dict and 1) *does NOT have* or 2) *has* words within edit distance

        self.name_freq_first = 0.0
        self.name_freq_last = 0.0

        # frequency of occurrence in these reference types? like how often does "will" appear as a public figure in our knowledge database
        self.ref_pop_culture = 0
        self.ref_public_figure = 0

        self.idable_probs = []

        self.extra_pos = ''

        self.pii_pattern = False

    # change token name
    def set_name(self,token):
        self.text = token

    # helper for update_counts, just increments the corresponding member
    def increment_count(self,count):
        if(count == 'num beginnings'):
            self.num_beginnings += 1  # NOTE: after adding in hello redacted, just counts all instances
        elif(count == 'num caps'):
            self.num_caps += 1
        elif(count == 'num middles'):
            self.num_middles += 1
        else:
            self.total_count += 1

    # update the members that keep track of identifiable instances
    def update_counts(self,count_list):
        for count in count_list:
            self.increment_count(count)

    # update/add values to any dictionary members, e.g. parts of speech
    def update_dict(n_dict,item):
        if item in n_dict.keys():  # could be more efficient
            n_dict[item] += 1
        else:
            n_dict[item] = 1

    # accessor functions in case we want to change privacy of vars later idk this is a later problem
    def get_name(self):
        return self.text

    def get_total_count(self):
        return self.total_count

    # for printing and test stuff
    def __str__(self):
        # tok_str = str(self.text) + ',' + str(self.total_count) + ',\"' +\
        #     str(self.utterance_lengths) + '\",\"' + str(self.pos) + '\",' +\
        #     str(self.num_caps) + ',' + str(self.num_beginnings) + ',' +\
        #     str(self.num_middles) + ',' + str(self.first_index) + ',' +\
        #     str(self.edit_count_one) + ',' + str(self.edit_count_two) + ',\"' +\
        #     str(self.related_tokens) + '\"'
        tok_str = str(self.text) + ',' + str(self.total_count) + ',' +\
            str(self.num_caps) + ',' + str(self.num_beginnings) + ',' +\
            str(self.num_middles) + ',' + str(self.context_words) + ',' +\
            str(self.context_words_capital) + ',' +\
            str(self.context_words_mid_cap) + str(self.related_tokens[0]) # + ',\"' + str(self.pos) + '\",'
        return tok_str