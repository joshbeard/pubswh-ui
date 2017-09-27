__author__ = 'jameskreft'

import requests
import feedparser
import re
import json
import arrow
import natsort
from urlparse import urljoin
from copy import deepcopy
from operator import itemgetter
from pubs_ui import app
from bs4 import BeautifulSoup
from dcxml import simpledc

from ..custom_filters import display_publication_info

json_ld_id_base_url = app.config.get('JSON_LD_ID_BASE_URL')
# should requests verify the certificates for ssl connections
verify_cert = app.config['VERIFY_CERT']
base_search_url = app.config['BASE_SEARCH_URL']
altmetric_key = app.config['ALTMETRIC_KEY']
altmetric_endpoint = app.config['ALTMETRIC_ENDPOINT']


def pubdetails(pubdata):
    """
    build the ordered list to make the 'Publications details' box

    :param pubdata: the data pulled from the pubs warehouse web service
    :return: pubdata with an additional "details" element
    """

    pubdata['details'] = []
    # details list element has len of 2 or 3.  If 2, the item is coming back as a simple Key:value object, but if three
    # there are either lists or dicts. the first item in the list is the param in pubdata, the 2nd or 3rd is the display
    # descriptor and the second if it exists is the secondary key needed to get the text.
    detailslist = [
        ['publicationType', 'text', 'Publication type:'],
        ['publicationSubtype', 'text', 'Publication Subtype:'],
        ['title', 'Title:'],
        ['seriesTitle', 'text', 'Series title:'],
        ['seriesNumber', 'Series number:'],
        ['subseriesTitle', 'Subseries:'],
        ['chapter', 'Chapter:'],
        ['subchapterNumber', 'Sub-chapter:'],
        ['issn', 'online', 'ISSN (online):'],
        ['issn', 'print', 'ISSN (print):'],
        ['isbn', 'ISBN:'],
        ['doi', 'DOI:'],
        ['edition', 'Edition:'],
        ['volume', 'Volume:'],
        ['issue', 'Issue:'],
        ['publicationYear', 'Year Published:'],
        ['language', 'Language:'],
        ['publisher', 'Publisher:'],
        ['publisherLocation', 'Publisher location:'],
        ['costCenters', 'text', 'Contributing office(s):'],
        ['productDescription', 'Description:'],
        ['numberofPages', 'Number of pages:'],
        ['largerWorkType', 'text', 'Larger Work Type:'],
        ['largerWorkSubtype', 'text', 'Larger Work Subtype:'],
        ['largerWorkTitle', 'Larger Work Title:'],
        ['startPage', 'First page:'],
        ['endPage', 'Last page:'],
        ['publicComments', 'Public Comments:'],
        ['temporalStart', 'Time Range Start:'],
        ['temporalEnd', 'Time Range End:'],
        ['conferenceTitle', 'Conference Title:'],
        ['conferenceLocation', 'Conference Location:'],
        ['conferenceDate', 'Conference Date:'],
        ['country', 'Country:'],
        ['state', 'State:'],
        ['county', 'County:'],
        ['city', 'City:'],
        ['otherGeospatial', 'Other Geospatial:'],
        ['datum', 'Datum:'],
        ['projection', 'Projection:'],
        ['scale', 'Scale:'],
        ['onlineOnly', 'Online Only (Y/N):'],
        ['additionalOnlineFiles', 'Additional Online Files (Y/N):']

    ]
    for detail in detailslist:

        if len(detail) == 3:
            # if the detail exists and is a dict with a couple key:value pairs, get the right value
            if pubdata.get(detail[0]) is not None and isinstance(pubdata.get(detail[0]), dict):
                pubdata['details'].append({detail[2]: pubdata[detail[0]].get(detail[1])})
            # if the thing is a list of dicts and if there is something in the list,
            # concatenate the values into a string
            elif pubdata.get(detail[0]) is not None and isinstance(pubdata.get(detail[0]), list) \
                    and len(pubdata.get(detail[0])) > 0:
                dd = []
                for det in pubdata.get(detail[0]):
                    dd.append(det.get(detail[1]))
                dd = ', '.join(filter(None, dd))
                pubdata['details'].append({detail[2]: dd})
        elif len(detail) == 2 and pubdata.get(detail[0]) is not None and len(pubdata.get(detail[0])) > 0:
            pubdata['details'].append({detail[1]: pubdata.get(detail[0])})
    return pubdata


def manipulate_doi_information(pubdata):
    """
    takes the DOI and adds it to the link structure
    :param pubdata: original pub data
    :return: manipulated pub data
    """
    if pubdata.get('doi') is not None and pubdata.get('publicationSubtype', {}).get('text') != \
            ('USGS Numbered Series' or 'USGS Unnumbered Series'):
        index_link = {
            "rank": None,
            "text": "Publisher Index Page (via DOI)",
            "type": {
                "id": 15,
                "text": "Index Page"
            },
            "url": "https://doi.org/" + pubdata['doi']
        }
        if pubdata.get('chorus'):
            chorus = deepcopy(pubdata['chorus'])
            if chorus.get('publiclyAccessibleDate'):
                index_link['linkHelpText'] = 'Publicly accessible after ' + chorus['publiclyAccessibleDate'] + \
                                             ' (public access data via <a href="http://www.chorusaccess.org" ' \
                                             'title="link to Chorus.org homepage">CHORUS</a>)'

        if pubdata.get('links'):
            pubdata['links'].append(index_link)
        else:
            pubdata['links'] = [index_link]
    return pubdata


def create_display_links(pubdata):
    """
    restructures links from the API so that they are easy to display in a jinja template
    :param pubdata:
    :return: pubdata with new displayLinks array
    """

    display_links = {
        'Abstract': [],
        'Additional Report Piece': [],
        'Appendix': [],
        'Application Site': [],
        'Authors Website': [],
        'Chapter': [],
        'Companion Files': [],
        'Cover': [],
        'Database': [],
        'Data Release': [],
        'Digital Object Identifier': [],
        'Document': [],
        'Errata': [],
        'Figure': [],
        'Illustration': [],
        'Image': [],
        'Index Page': [],
        'Metadata': [],
        'Plate': [],
        'Sheet': [],
        'Table': [],
        'Dataset': [],
        'Project Site': [],
        'Raw Data': [],
        'Read Me': [],
        'Referenced Work': [],
        'Related Work': [],
        'Spatial Data': [],
        'Thumbnail': [],
        'Version History': []
    }
    links = deepcopy(pubdata.get("links"))
    # sort links into the different link types

    for key, value in display_links.iteritems():
        for link in links:
            if link['type']['text'] == key:
                value.append(link)
    # smash index page and plate links around
    display_links = manipulate_plate_links(display_links)
    display_links = manipulate_index_page_links(display_links)
    # shove a rank onto everything that doesn't have one
    for key, value in display_links.iteritems():
        rank_counter = 1
        for link in value:
            if link.get("rank") is None:
                link['rank'] = rank_counter
                rank_counter += 1

    pubdata["displayLinks"] = display_links
    # set a variable so that we can display something if the pub has no links other than a thumbnail
    pub_has_no_links = True
    for key, value in display_links.iteritems():
        if key != 'Thumbnail' and len(value) > 0:
            pub_has_no_links = False
    pubdata['pubHasNoLinks'] = pub_has_no_links
    return pubdata


def manipulate_index_page_links(display_links):
    """
    This function rejiggers display text for index page links
    :param display_links:
    :return:
    """
    # only do something if there are links in the index page links section
    if len(display_links.get('Index Page')) > 0:
        for link in display_links["Index Page"]:
            if link.get("text") is None and 'pubs.usgs.gov' in link["url"]:
                link["text"] = "USGS Index Page"
                link["rank"] = 1
            elif link.get("text") is None and 'ngmdb.usgs.gov' in link["url"]:
                link["text"] = "National Geologic Map Database Index Page"
                link["rank"] = 2
            elif link.get("text") is None:
                link["text"] = "Publisher Index Page"
                link['rank'] = 3
            elif link.get("text") == "Publisher Index Page (via DOI)":
                link['rank'] = 4
    return display_links


def manipulate_plate_links(display_links):
    """
    This function rejiggers plate link displays for plate links that are named regularly but do not have display text or
    a proper order
    :param display_links: the
    :return: display links with rejiggered plate link order
    """
    # only do something if there are links in the plate links section
    if len(display_links.get("Plate")) > 0:
        for link in display_links["Plate"]:
            url = link["url"]
            file_name = url.split("/")[-1].split(".")
            text = file_name[0]
            if link.get("text") is None:
                if len(file_name[0].title().split('-')) > 1:
                    try:
                        text = file_name[0].title().split('-')
                        text[1] = int(text[1])
                        link['rank'] = text[1]
                    except (ValueError, IndexError):
                        text = file_name[0].title().split('-')
                if len(file_name[0].split("_")) > 1:
                    try:
                        text = file_name[0].split("_")[-1]
                        text = re.split('(\d+)', text)[0:2]
                        text[1] = int(text[1])
                        link['rank'] = text[1]
                    except (ValueError, IndexError):
                        try:
                            text = file_name[0].split("_")[0]
                            text = re.split('(\d+)', text)[0:2]
                            text[1] = int(text[1])
                            link['rank'] = text[1]
                        except (ValueError, IndexError):
                            text = file_name[0].split("_")

                link["text"] = text
                try:
                    link['text'][1] = str(link['text'][1])
                    link['text'] = " ".join(link['text']).title()
                except (ValueError, TypeError, IndexError):
                    link['text'] = str(link["text"]).title()
            if link.get('linkFileType') is None:
                try:
                    link['linkFileType'] = {'text': file_name[1]}
                except IndexError:
                    link['linkFileType'] = None
        display_links["Plate"] = sorted(display_links["Plate"], key=itemgetter('text'))
    return display_links


def pull_feed(feed_url):
    """
    pull page data from a my.usgs.gov confluence wiki feed
    :param feed_url: the url of the feed, created in confluence feed builder
    :return: the html of the page itself, stripped of header and footer
    """
    feed = feedparser.parse(feed_url)

    # Process html to remove unwanted mark-up and fix links
    post = ''
    if len(feed['entries']) > 0:
        soup = BeautifulSoup(feed['entries'][0].summary, 'lxml')

        # Remove edited by paragraph
        soup.p.extract()

        # Remove final div in the feed
        feed_div = soup.find('div', class_='feed')
        children_divs = feed_div.findAll('div')
        children_divs[len(children_divs) - 1].extract()

        # Translate any in page links to use relative URL
        base = feed['entries'][0].summary_detail.base
        links = feed_div.select('a[href^="' + base + '"]')
        for link in links:
            link['href'] = link['href'].replace(base, '')
        post = unicode(soup)

    return post


class SearchPublications(object):
    
    """
    Methods for executing various types
    of searches against the backend
    Pubs API.
    
    :param str search_url: URL without any search parameters appended
    """
    
    def __init__(self, search_url):
        self.search_url = search_url
        
    def get_pubs_search_results(self, params=None):
        """
        Searches Pubs API for a specified query parameter

        :param dict params: dictionary of form {'key1': 'value1', 'key2': 'value2}
        :return: query results (or None) and response status code.
        :rtype: tuple
        """

        search_result_obj = requests.get(url=self.search_url, params=params, verify=verify_cert)
        search_result_json = None
        if search_result_obj.status_code == requests.codes.ok:
            try:
                search_result_json = search_result_obj.json()
            except ValueError:
                pass
            else:
                #TODO: Refactor to add the additional dictionary keys where needed. This simplifies this function so that
                # just returns the json result.
                for record in search_result_json.get('records', []):
                    contributor_lists(record)

        return search_result_json, search_result_obj.status_code


def contributor_lists(record):
    """

    :param record: The full pubs record
    :return: The pub record with two kinds of additional lists- one with
    concatenated names and another with concatenated names and types
    """

    #TODO: Refactor to make clear this updates record in place and don't return record. Consider whether contributor_types should
    # be hardcoded or fetched from pub service lookup.
    contributor_types = ['authors', 'editors', 'compilers']
    for contributor_type in contributor_types:
        if record.get('contributors') is not None:
            if record['contributors'].get(contributor_type) is not None:
                record[contributor_type+"List"] = make_contributor_list(record['contributors'][contributor_type])
                record[contributor_type+"ListTyped"] = \
                    concatenate_contributor_names(record['contributors'][contributor_type])
    return record


def make_contributor_list(contributors):
    """
    Makes a list of names for contributors regardless of type that is easy to join in jinja.  Useful when you need
    a list of names and don't have to do all of the semantic jiggery-poky that one needs for names otherwise.

    :param list contributors: a list of dicts of a contributor type (authors, editors, etc)
    :return list of concatenated author names in given family suffix or corporate name
    :rtype: list
    """
    # turn the list of dicts into smaller, sorted list of dicts
    typed_contributor_list = concatenate_contributor_names(contributors)
    # only grab the string portion of the tuple, put it into its own list.
    contributor_list = []
    for contributor in typed_contributor_list:
        contributor_list.append(contributor.get("text"))
    return contributor_list


def concatenate_contributor_names(contributors):
    """
    Turns a dict with a lot of split-out contributor information into a simpler format of ("kind", "name")

    :param list contributors: a list of dicts of a contributor type (authors, editors, etc)
    :return:
    """
    # Sort the contributors by the rank that comes out of the web service- ranks is something that will always be there
    # (it is fundamental to the pubs data model, so we don't have to deal with it not being there
    sorted_contributors = sorted(contributors, key=itemgetter('rank'))
    # empty list to build the names
    contributor_list = []
    for contributor in sorted_contributors:
        # test for the boolean "corporation" flag for each contributor
        if contributor['corporation'] is False:
            # list to set up join
            contributor_name_list = []
            contributor_dict = {"type": "person"}
            # add parts of name to the list if they exist and aren't empty strings
            if contributor.get("given") is not None and len(contributor.get("given")) > 0:
                contributor_name_list.append(contributor['given'])
            if contributor.get("family") is not None and len(contributor.get("family")) > 0:
                contributor_name_list.append(contributor['family'])
            if contributor.get("suffix") is not None and len(contributor.get("suffix")) > 0:
                contributor_name_list.append(contributor['suffix'])
            contributor_dict["text"] = " ".join(contributor_name_list)
            if contributor.get("orcid"):
                contributor_dict["orcid"] = contributor['orcid']
            if contributor.get("email"):
                contributor_dict["email"] = contributor["email"]

        # corporate authors- the other side of the boolean
        else:
            contributor_dict = {"type": 'corporation', "text": contributor.get('organization')}
        contributor_list.append(contributor_dict)
    return contributor_list


def update_geographic_extents(record):
    """
    Takes the string geographicExtents and translates it to a dictionary representing a geojson object. Properties in
    the geojson object are filled in from other values in the dictionary. If the geographicExtents can not be parsed
    into a valid geojson, the key is deleted from the dictionary
    :param record: represents a publication and is modified by this function
    :type record dict
    """
    result = None

    if record.has_key('geographicExtents'):
        try:
            geojson = json.loads(record.get('geographicExtents'))
        except ValueError as e:
            app.logger.info("Prod ID " + str(record.get('id')) + " geographicExtents json parse error: " + repr(e))

        else:
            featureId = record.get('indexId') + '.base_id'
            properties = {'title': record.get('title'),
                          'id': record.get('indexId'),
                          'url': json_ld_id_base_url + 'publication/' + record.get('indexId'),
                          'year': record.get('publicationYear'),
                          'info': display_publication_info(record)
                          }

            if geojson.get('type') == "FeatureCollection":
                result = geojson
            elif geojson.get('geometry'):
                result = {'type': 'FeatureCollection',
                          'features': [geojson]}
            result['properties'] = {'title': record.get('title')}

            for feature in result.get('features', []):
                feature.update({'id': featureId, 'properties': properties})

        if result:
            record['geographicExtents'] = result
        elif record.has_key('geographicExtents'):
            del record['geographicExtents']


def create_store_info(publication_resp):
    """
    Create context that can be displayed in a Jinja
    Template for publications with USGS Store data.

    :param requests.Response publication_resp: response object for a publication returned from a GET request on
                                               the /publication service.
    :return: dict containing two items:
        'context_id': the index (prod) ID of the context pub. Included as 
            confirmation only; identical to the 'context_id' param.
        'offers': the object that contains a representations of the USGS store offer for the publication
    """
    index_id = None
    product = None
    offers = None

    if publication_resp.status_code == 200:
        response_json = publication_resp.json()
        index_id = response_json.get('indexId')
        if 'stores' in response_json.keys():
            stores = response_json['stores']
            if len(stores) > 0:
                product = stores[0]

    # REMARKS ABOUT SERVICE RETURNED VALUE ASSUMPTIONS
    #
    # The service returns JSON, which is converted into Python structures.
    #
    #
    # Concerning the sense of the terminology, the occurrence of 
    # '"@type": "succeeding"' or '"@type": "preceding"' refers to the 
    # relationship of the linked pub TO the context pub. 
    #
    # To put it another way, the "@type" relationship descriptor assumes 
    # that the linked pub is the SUBJECT, and the context pub is the OBJECT. 
    # This can be subtly confusing for those of us who have absorbed the RDF 
    # conventions about framing the predicate from the viewpoint of the subject.
    # 
    # Just think of the @type as saying "This linked pub is ___ the context pub."
    if product is not None:
        # check if the product is in stock or not
        product_availability = 'schema:InStock' if product.get('available') else 'schema:OutOfStock'
        # build the offers object
        offers = {
            "@context":
                {"schema": "http://schema.org/"},
            "@type": "schema:ScholarlyArticle",
            "schema:offers": {
                "@type": "schema:Offer",
                "schema:availability": product_availability,
                "schema:price": product.get('price'),
                "schema:priceCurrency": "USD",
                "schema:url": product.get('store'),
                "schema:seller": {
                    "@type": "schema:Organization",
                    "schema:name": "USGS Store",
                    "schema:url": "http://store.usgs.gov"}
                }
            }
    return {'context_item': index_id, 'offers': offers}


def add_relationships_graphs(context_pubdata, supersedes_service_url, url_root):
    """
    Accepts publication data JSON for the desired context publication,
    extracts the context publication's index_id, calls precedes_supersedes_url
    for that index_id. If the current publication supersedes, and/or
    is superseded by, any other publications, inserts summary info about 
    those pubs into the passed context_pubdata. 


    context_pubdata: the Python decode of the JSON representation of the 
        context publication.  the most important elements here is called "interactions"
    supersedes_service_url: the endpoint of the service from which info about
        related items should be obtained
    param pubs_base_url: the url needed to compose a publication URL given 
        a known prod_id
    """
    
    base_id_url = urljoin(url_root, 'publication/')
    return_pubdata = deepcopy(context_pubdata)
    index_id = context_pubdata['indexId']
    pub_url = urljoin(base_id_url, index_id)

    # this LITERAL is probably OK for this particular use. However, it
    # needs to be exported to a configuration.
    pub_type = 'rdac:Work'
    
    # obtain data from legacy api (down to just store data now)
    # pre_super = legacy_api_info(index_id, supersedes_service_url)
    pre_super = {"offers": None}
    # get interactions from the new endpoint to build json-LD object
    interactions = return_pubdata.get('interactions')

    if interactions is not None:

        # ensure 'relationships' is set up
        if 'relationships' not in return_pubdata:
            return_pubdata['relationships'] = {}
        if '@context' not in return_pubdata['relationships']:
            return_pubdata['relationships']['@context'] = {}
        if '@graph' not in return_pubdata['relationships']:
            return_pubdata['relationships']['@graph'] = []
        # build @context object
        # namespaces
        return_pubdata['relationships']['@context']['dc'] = 'http://purl.org/dc/elements/1.1/'
        return_pubdata['relationships']['@context']['xsd'] = 'http://www.w3.org/2001/XMLSchema#'
        return_pubdata['relationships']['@context']['rdac'] = 'http://rdaregistry.info/Elements/c/'
        return_pubdata['relationships']['@context']['rdaw'] = 'http://rdaregistry.info/Elements/w/'
        # relationships
        return_pubdata['relationships']['@context']['rdaw:replacedByWork'] = {'@type': '@id'}
        return_pubdata['relationships']['@context']['rdaw:replacementOfWork'] = {'@type': '@id'}

        # build @graph object
        # add base/context record
        return_pubdata['relationships']['@graph'].append({
            '@id': pub_url,
            '@type': pub_type,
            'dc:title': return_pubdata.get('title'),
            'dc:date': str(return_pubdata.get('publicationYear'))
        }
        )

        for interaction in interactions:
            # add any linked data for superseding another publication
            if interaction['predicate'] == "SUPERSEDED_BY" and interaction['object']['indexId'] \
                    == return_pubdata['indexId']:
                related_pub = {
                    '@id':  urljoin(base_id_url, interaction['subject']['indexId']),
                    '@type': pub_type,
                    'dc:title': interaction['subject']['title'],
                    "rdaw:replacedByWork": pub_url}
                if interaction['subject']['publicationYear']:
                    related_pub['dc:date'] = interaction['subject']['publicationYear']
                return_pubdata['relationships']['@graph'].append(related_pub)
            # add any linked data for being superseded by another publication
            if interaction['predicate'] == "SUPERSEDED_BY" and interaction['subject']['indexId'] \
                    == return_pubdata['indexId']:
                related_pub = {
                    '@id':  urljoin(base_id_url, interaction['object']['indexId']),
                    '@type': pub_type,
                    'dc:title': interaction['object']['title'],
                    "rdaw:replacementOfWork": pub_url}
                if interaction['object']['publicationYear']:
                    related_pub['dc:date'] = interaction['object']['publicationYear']
                return_pubdata['relationships']['@graph'].append(related_pub)

    # add offer data from the USGS store if it exists
    if pre_super['offers']:
        return_pubdata['offers'] = pre_super['offers']
    return return_pubdata


def change_to_pubs_test(pubs_url):
    """
    flips pubs urls to pubs-test urls to work around annoying apache config on test tier
    :param pubs_url: a pubs.er.usgs.gov url
    :return: a pubs-test.er.usgs.gov url
    """
    pubs_test_url = pubs_url.replace('pubs.er', 'pubs-test.er')
    return pubs_test_url


def make_chapter_data_for_display(pubdata):
    """
    take publication data and munges it around to make it easy to work with in jinja templates
    :param pubdata:  data for a single publication from the pubs-services endpoint
    :return: pubdata
    """
    if len(pubdata.get('interactions')) > 0:
        # natural sort the indexIDs so that chapter 2 comes after chapter one and before chapter three
        pubdata['interactions'] = natsort.natsorted(pubdata['interactions'], key=lambda x: x['subject']['indexId'],
                                                    alg=natsort.ns.IGNORECASE)
        # determine wheter to display the publication subparts chunk of the template
        for interaction in pubdata['interactions']:
            if interaction['predicate'] == "IS_PART_OF" and interaction['subject']['indexId'] != pubdata['indexId']:
                pubdata['hasSubParts'] = True
            else:
                pubdata['hasSubParts'] = False
    return pubdata


def munge_pubdata_for_display(pubdata, replace_pubs_with_pubs_test, supersedes_url, json_ld_id_base_url):
    """
    Takes publication data from the pubs-services API and smashes it around so that it is friendly for jinja2 templates
    :param pubdata: data for a single publication from the pubs-services endpoint
    :return: pubdata
    """
    pubdata = pubdetails(pubdata)
    pubdata = add_relationships_graphs(pubdata, supersedes_url, json_ld_id_base_url)
    pubdata = manipulate_doi_information(pubdata)
    pubdata = create_display_links(pubdata)
    pubdata = contributor_lists(pubdata)
    update_geographic_extents(pubdata)
    pubdata = make_chapter_data_for_display(pubdata)
    pubdata['formattedModifiedDateTime'] = arrow.get(pubdata['lastModifiedDate']).format('MMMM DD, YYYY HH:mm:ss')
    pubdata = munge_abstract(pubdata)
    pubdata = has_excel(pubdata)
    # Following if statement added to deal with Apache rewrite of pubs.er.usgs.gov to pubs-test.er.usgs.gov.
    # Flask_images creates a unique signature for an image e.g. pubs.er.usgs.gov/blah/more_blah/?s=skjcvjkdejiwI
    # The Apache rewrite changes this to pubs-test.er.usgs.gov/blah/more_blah/?s=skjcvjkdejiwI, where there is
    # no image with the signature 'skjcvjkdejiwI' which leads to a failure to find the image. Instead of allowing
    # Apache to do the rewrite, this code snippet executes the rewrite so the correct signature is preserved for
    # a given image URL.
    if replace_pubs_with_pubs_test:
        pubdata['displayLinks']['Thumbnail'][0]['url'] = change_to_pubs_test(
            pubdata['displayLinks']['Thumbnail'][0]['url'])
    return pubdata


def has_excel(pubdata):
    """
    sets a display variable so that if there is an excel document, we can display a link to an excel reader
    :param pubdata:
    :return: pubdata
    """
    pubdata['hasExcel'] = False
    if pubdata.get('links') is not None:
        for link in pubdata['links']:
            if link.get('linkFileType', {}).get('text') == 'xlsx':
                pubdata['hasExcel'] = True
    return pubdata


def sort_list_of_dicts(list_to_be_sorted, key_name, reverse=False):
    """
    Sort a list of dictionaries by a specified key.
    
    :param list list_to_be_sorted: list of dictionaries to be sorted
    :param str key_name: key in the dictionaries to be sorted by
    :param bool reverse: should the dictionaries be sorted in descending order
    :return: sorted list of dictionaries by specified key
    :rtype: list
    
    """
    new_list = sorted(list_to_be_sorted, key=itemgetter(key_name), reverse=reverse)
    return new_list


def extract_related_pub_info(pubdata):
    """
    Take some json-ld publication and extract the 
    information for preceding and superseding
    publications. If no preceding or superseding
    information is present, empty lists are returned
    for each.
    
    :param dict pubdata: publication JSON data
    :return: a dictionary containing a list containing dictionaries of related publication information
    :rtype: dict
    
    """
    preceding_info = []  # this list may have multiple elements in it
    superceding_info = []  # this list should never have more than 1 element in it
    graph = pubdata.get('relationships', {}).get('@graph', [])
    related_pubs = []
    for graph_element in graph:
        if graph_element.has_key('rdaw:replacedByWork') or graph_element.has_key('rdaw:replacementOfWork'):
            related_pubs.append(graph_element)
    related_length = len(related_pubs)
    if related_length == 0:
        relations = {'precede_len': 0,
                     'supersede_len': 0,
                     'precede_info': [],
                     'supersede_info': []
                     }
    elif related_length >= 1:
        for related_pub in related_pubs:
            item_year = related_pub['dc:date']
            item_title = related_pub['dc:title']
            # provides an absolute URL, but this extracts the id so a relative URL can be made
            item_id = related_pub['@id'].rsplit('/', 1)[1]
            item_info = {'id': item_id,
                         'title': item_title,
                         'year': item_year
                         }
            if related_pub.has_key('rdaw:replacedByWork'):
                preceding_info.append(item_info)
            elif related_pub.has_key('rdaw:replacementOfWork'):
                superceding_info.append(item_info)
        relations = {'precede_len': len(preceding_info),
                     'supersede_len': len(superceding_info),
                     'precede_info': sort_list_of_dicts(preceding_info, 'year'),
                     'supersede_info': sort_list_of_dicts(superceding_info, 'year')
                     }
    else:
        raise Exception('Failed to parse supersede information.')
    return relations


def munge_abstract(pubdata):
    """
    Take an abstract, and if there is an h1 tag in there, take it out and put the contents in the abstract_label object,
    else put abstract in there.  This is a hack until we can change the abstract type.
    :param pubdata: data about a publication
    :return:
    """
    if pubdata.get('docAbstract') is not None:
        abstract = deepcopy(pubdata['docAbstract'])
        soup = BeautifulSoup(abstract, "lxml")
        # find the h1 tag
        if soup.find('h1') is not None:
            possible_header = soup.find('h1').contents[0]
            soup.h1.extract()
            abstract = str(soup)
            pubdata['docAbstract'] = abstract
            abstract_header = possible_header
        else:
            abstract_header = 'Abstract'
    else:
        abstract_header = 'Abstract'

    pubdata['abstractHeader'] = abstract_header

    return pubdata

def generate_dublin_core(pubrecord):
    """
    This function turns a publication record into a simple dublin core XML record
    :param pubrecord:
    :return: dublin core XML record
    """
    data = {
            "contributors": pubrecord.get('authorsList')[1:],
            "creators": [pubrecord.get('authorsList')[0]],
            "dates": [pubrecord.get('publicationYear')],
            "descriptions": [pubrecord.get('docAbstract')],
            "formats": ['application/pdf'],
            "identifiers": [pubrecord.get('doi')],
            "languages": ['en'],
            "publishers": [pubrecord.get('publisher')],
            "titles": [pubrecord.get('title')],
            }
    return '\n'.join(simpledc.tostring(data).splitlines()[1:])

def generate_sb_data(pubrecord, replace_pubs_with_pubs_test, supersedes_url, json_ld_id_base_url):
    """
    This function transforms data from the Publications Warehouse data model to the the ScienceBase data model so that
    Publications Warehouse data can be pushed to ScienceBase
    :param pubrecord: the publication record that is coming out of the publication warehouse web service
    :param replace_pubs_with_pubs_test: Needed for munging pubs data we have to do to support pubs-test horribleness
    :param supersedes_url: needed for munging pubs data function- supports supersedes
    :param json_ld_id_base_url: needed for generating json-ld in munge pubdata
    :return: sciencebase data that follows the sciencebase data model:
    https://my.usgs.gov/confluence/display/sciencebase/ScienceBase+Item+Core+Model
    """
    pubdata = munge_pubdata_for_display(pubrecord, replace_pubs_with_pubs_test, supersedes_url, json_ld_id_base_url)
    sbdata= {"title": pubdata.get('title'),
             "id": pubdata.get('scienceBaseUri'),
             "identifiers": [
                 {
                    "type": "local-index",
                    "scheme": "unknown",
                    "key": pubdata['indexId']
                    },
                    {
                    "type": "local-pk",
                    "scheme": "unknown",
                    "key": pubdata['id']
                    }
             ],
             "body": pubdata.get('docAbstract'),
             "citation": pubdata.get('usgsCitation'),
             "contacts": [],
             "facets": [],
             "dates": [],
             "tags": [],
             "browseCategories": [
                 "Publication"
             ],
             "browseTypes": [
                 "Citation"
             ],
             'webLinks': [
                 {
                     "type": "webLink",
                     "uri": "http://pubs.er.usgs.gov/publication/"+pubdata['indexId'],
                     "rel": "related",
                     "title": "Publications Warehouse Index Page",
                     "hidden": False
                 }
             ],
             "parentId": app.config['SCIENCEBASE_PARENT_UUID']
             }

    if pubdata.get('doi'):
        doi_object = {
            "type": "doi",
            "scheme": "http://www.loc.gov/standards/mods/mods-outline-3-5.html#identifier",
            "key": "doi:"+pubdata['doi']
        }
        sbdata['identifiers'].append(doi_object)
    if pubdata.get('seriesTitle'):
        series_object = {
            "type": "series",
            "scheme": "unknown",
            "key": pubdata['seriesTitle'].get('text')
        }
        sbdata['identifiers'].append(series_object)
        title_tag = {
            "type": "Publication",
            "scheme": "USGS Publications Warehouse",
            "name": pubdata['seriesTitle']['text'][:78] if pubdata['seriesTitle'].get('text') else None
        }
        sbdata['tags'].append(title_tag)
    if pubdata.get('publicationYear'):
        publication_year = {
            "type": "Publication",
            "dateString": pubdata['publicationYear'],
            "label": "Publication Date"
        }
        sbdata['dates'].append(publication_year)
    if pubdata.get('contributors', {}).get('authors'):
        if pubdata.get('authorsListTyped'):
            for author in pubdata['authorsListTyped']:
                contact = {}
                contact['type'] = "Author"
                contact['name'] = author.get('text')
                contact['email'] = author.get('email')
                if author['type'] == 'person':
                    contact['contactType'] = "person"
                else:
                    contact['contactType'] = "organization"
                sbdata['contacts'].append(contact)
        if pubdata.get('contributors', {}).get('editors'):
            if pubdata.get('editorsListTyped'):
                for editor in pubdata['authorsListTyped']:
                    contact = {}
                    contact['type'] = "Editor"
                    contact['name'] = editor.get('text')
                    contact['email'] = editor.get('email')
                    if editor['type'] == 'person':
                        contact['contactType'] = "person"
                    else:
                        contact['contactType'] = "organization"
                    sbdata['contacts'].append(contact)
    if pubdata.get('publisher'):
        sbdata['contacts'].append({"name": pubdata['publisher'], "type": "Publisher"})
    for (linktype, linklist) in pubdata['displayLinks'].items():
        if linktype == "Thumbnail" and len(linklist) == 1:
            thumbnail_link = {
                        "type": "browseImage",
                        "uri": linklist[0]['url'],
                        "rel": "related",
                        "title": "Thumbnail",
                        "hidden": False
                        }
            sbdata["webLinks"].append(thumbnail_link)
        if linktype == "Document" and len(linklist) >= 1:
            for link in linklist:
                document_link = {
                        "type": "pdf",
                        "uri": link['url'],
                        "rel": "related",
                        "title": link['text'] if link.get('text') else "Document",
                        "hidden": False
                        }
                sbdata["webLinks"].append(document_link)
        if linktype == "Data Release" and len(linklist) >= 1:
            for link in linklist:
                document_link = {
                        "type": "webLink",
                        "uri": link['url'],
                        "rel": "related",
                        "title": link['text'] if link.get('text') else "USGS Data Release",
                        "hidden": False
                        }
                sbdata["webLinks"].append(document_link)
    # Set the citation facet
    citation_facet = {
        "citationType": pubdata.get('publicationType', {}).get('text'),
        "journal": pubdata.get('seriesTitle', {}).get('text'),
        "edition": pubdata.get('edition'),
        "tableOfContents": pubdata.get('tableOfContents'),
        "conference": pubdata.get('conferenceTitle'),
        "language": pubdata.get('language'),
        "note": "",
        "parts": [],
        "className": "gov.sciencebase.catalog.item.facet.CitationFacet"
    }

    if pubdata.get('volume'):
        volume = {
            "type": "volume",
            "value": pubdata.get('volume')
        }
        citation_facet['parts'].append(volume)

    if pubdata.get('issue'):
        issue = {
            "type": "issue",
            "value": pubdata.get('issue')
        }
        citation_facet['parts'].append(issue)
    if pubdata.get('publisherLocation'):
        location = {
            "type": "Publication Place",
            "value": pubdata.get('publisherLocation')
        }
        citation_facet['parts'].append(location)
    sbdata['facets'].append(citation_facet)

    return sbdata


def get_altmetric_badge_img_links(publication_doi, altmetric_service_endpoint=altmetric_endpoint,
                                  altmetric_key=altmetric_key, verify=verify_cert):
    """
    Get the links for small, medium, and altmetric badges, and the link
    that provides further information about the attention score in the badge.
    This function will return None values if altmetric returns a 404 or an
    invalid DOI value causes a requests.ConnectionError.

    :param str publication_doi: DOI for a publication
    :param str altmetric_service_endpoint: altmetric service endpoint
    :param str altmetric_key: a key so this function can access the badges USGS is paying for
    :param bool verify: boolean specifying whether requests should verify SSL certs
    :return: badge links if they are available and the link to a page that provides further details about the badge
    :rtype: tuple

    """
    altmetric_badge_imgs = None
    altmetric_details = None
    if publication_doi is not None:
        parameters = {'key': altmetric_key}
        publication_endpoint = urljoin(altmetric_service_endpoint, 'doi/{}'.format(publication_doi))
        try:
            resp = requests.get(publication_endpoint, params=parameters, verify=verify)
        except requests.ConnectionError:
            pass
        else:
            if resp.status_code != 404:
                resp_json = resp.json()
                altmetric_badge_imgs = resp_json.get('images')
                altmetric_details = resp_json.get('details_url')
    return altmetric_badge_imgs, altmetric_details
