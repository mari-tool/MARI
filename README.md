# MARI

This is the \[currently anonymized\] repository for the Mostly Automated Redaction Interface (MARI) tool.

This work was created by researchers at \[University\] to address redacting identifiable information in unstructured text corpora.

To run the source code, proceed with the following steps.

## 1. Requirements
clear the pip cache if necessary:

`rm -rf ~/.cache/pip`

install packages:

`pip3 install cython==0.29.36`

`xargs -n1 pip install < requirements.txt` (or `pip3`)

`python -m spacy download en_core_web_lg` (or `en_core_web_sm`)

`sudo apt-get install python3-tk`

## 2. Running the application
navigate to the `application` folder. run
`python app.py` (or equivalent, e.g., `py` or `python3`)
