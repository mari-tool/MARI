import spacy
from spacy.tokens import Token
from tokenContainerClass import TokenContainer
from spacy.lang.en.stop_words import STOP_WORDS

###using abydos for ipa structure, might be a better option somewhere else
import abydos
from abydos import phonetic

import eng_to_ipa as ipa

peHolder = abydos.phonetic.Ainsworth()
#self.ipa = peHolder.encode(t_name)

# utterance in which the token was replaced?
Token.set_extension('original_utt',default='')

# IPA
Token.set_extension('ipa',default='')

Token.set_extension('start_sent',default=False)

Token.set_extension('contains_delimiter',default=False)  # possibly a compound token

Token.set_extension('prediction_vec',default=[])

Token.set_extension('prob_in_idable_category',default=0.0)

Token.set_extension('is_idable',default=False)

Token.set_extension('category',default='Non-identifiable')

# how common term is
Token.set_extension('frequency',default=0.0)

Token.set_extension('global_token',default=None)

Token.set_extension('global_token_id',default=-1)

Token.set_extension('dfile',default=None)

Token.set_extension('custom_replacement',default='')

Token.set_extension('is_ignored',default=False)

Token.set_extension('dictionary_flag',default=False)

#Token.set_extension('text_with_buf',default='')

#Token.set_extension('extra_pos',default='')

# for display purposes
Token.set_extension('lev_flag',default=False)

Token.set_extension('ipa_flag',default=False)


"""
sets the ipa format of a token
"""
# def __set_ipa__(token):
#     token._.ipa = peHolder.encode(token.text)

def __set_ipa__(token):
    tok_ipa = ipa.convert(token.text)  # words that cannot be found in the dictionary are simply reprinted with an asterisk
    if('*' not in tok_ipa):
        token._.ipa = tok_ipa
    else:
        token._.ipa = peHolder.encode(token.text)


"""
prints the token's attributes in csv format
TODO: remove or fix the way object attributes print
"""
def __csv_str__(token):
    tok_str = ''

    attribute_list = dir(token)
    for att in attribute_list:
        #if(att[:2] == '__' and att[-2:] == '__'):
        if(att[0] == '_'):
            continue
        if(tok_str == ''):
            tok_str = str(getattr(token,att))
        else:
            tok_str = tok_str + ',' + str(getattr(token,att))

    custom_list = dir(token._)
    for att in custom_list:
        if(att[0] == '_'):
            continue
        tok_str = tok_str + ',' + str(getattr(token._,att))

    return tok_str


"""
for testing purposes; otherwise, takes up too much space
"""
def __test_str__(token):
    """
    tok_str = str(token.text) + ',' + str(token._.is_dict_word) + ',' + str(token._.is_first_name) +\
            ',' + str(token._.is_last_name) + ',' + str(token._.is_city) + ',' +\
            str(token._.is_subcountry) + ',' + str(token._.is_country) + ',' +\
            str(token._.name_freq_first) + ',' + str(token._.name_freq_last) + ',' +\
            str(token.tag_)
    """

    # TEST
    custom_list = dir(token._)
    tok_str = ''
    for att in custom_list:
        if(att[0] == '_'):
            continue
        tok_str = tok_str + ',' + str(att) + ':' + str(getattr(token._,att))

    return tok_str


Token.set_extension('__set_ipa__', method=__set_ipa__, force=True)
Token.set_extension('__csv_str__', method=__csv_str__, force=True)
Token.set_extension('__test_str__', method=__test_str__, force=True)
