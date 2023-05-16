#--------------------------------------------------------------------------------------------------

# filename points to an existing, syntactically correct xml file able to be used for SOAP requests.
# Be ware! This script does no syntax validation
# If the file you're pointing to is not correct, GIGO will happen. 
filename = 'test.xml'

# These tags will be the beginning and end of processing. 
# Most likely, you don't need to touch it.
startingtag = '<soapenv:Body>'
closingtag = '</soapenv:Body>'

# Here you can specify values which if found in the xml you prefer to be replaced
# with a constant, or result of a function call. 
replacers = {
    "${=java.util.UUID.randomUUID()}": lambda: str(uuid.uuid4()),
    '?': 'null'
}

#--------------------------------------------------------------------------------------------------
# Note: Script does not handle arrays at the moment, as I did not need it to (yet). 
#--------------------------------------------------------------------------------------------------

import uuid
import types

def removecomments(line):
    start = '<!--'
    end = '-->'

    while start in line:
        startindex = line.index(start)
        endindex = line.index(end)
        line = line[:startindex] + line[endindex+3:]
    return line

def replacesingletags(line):
    start = '<'
    end = '/>'
    
    while start in line and end in line:
        startindex = line.index(start)
        endindex = line.index(end)
        tag = line[startindex+1:endindex]
        line = line.replace(f'<{tag}/>', f'<{tag}></{tag}>')
    return line

def extractContent(filename):
    content = ''
    with open(filename) as file:
        for line in file:
          
            line = removecomments(line)
            line = replacesingletags(line)
            content = content + line
    content = content.replace('\n', ' ')
    while '  ' in content:
        content = content.replace('  ', ' ')
    start = content.index(startingtag) + len(startingtag)
    end = content.index(closingtag)
    return content[start:end]

def getTag(content):
    if '<' not in content or '>' not in content:
        return content

    (start, end) = (content.index('<'), content.index('>'))
    tagNameWithAttributes = content[start + 1 : end]
    tagname = tagNameWithAttributes.split(' ')[0] if ' ' in tagNameWithAttributes else tagNameWithAttributes
    attributes = tagNameWithAttributes[tagNameWithAttributes.index(' ')::] if ' ' in tagNameWithAttributes else ''
    closingtag = f'</{tagname}>'

    if closingtag not in content:
        return content

    closingtagindex = content.index(closingtag)
    tagContent = content[end + 1 : closingtagindex]
    closingtagindex = closingtagindex+len(closingtag)
    tagdict = {
            'start': start,
            'end': closingtagindex, 
            'tagname': tagname,
            'attributes': attributes,
            'content': getTag(tagContent)
        }

    nexttag = getTag(content[closingtagindex::])
    if nexttag == content[closingtagindex::]:
        return tagdict
    else:
        out = [tagdict]        

        remainingcontent = ''
        while nexttag != remainingcontent:
            if type(nexttag) is dict:
                out.append(nexttag)
            elif type(nexttag) is list:
                for tag in nexttag:
                    out.append(tag)
            remainingcontent = content[out[-1]['end']::]
            nexttag = getTag(remainingcontent)

        return out

def extractAttributes(attributes):
    map = {}
    if len(attributes) == 0:
        return map

    attributes = attributes.strip()
    attributes = attributes.split(' ')
    for attribute in attributes:
        if '=' in attribute:
            split = attribute.split('=')
            key = split[0]
            value = '='.join(split[1::])
            map[key] = value[1:-1]
    return map

def processTags(tags, context=''):
    obj = {}
    if type(tags) is dict:
        key = f'{context}.{tags["tagname"]}' if len(context) > 0 else tags['tagname']
        obj[key] = processTags(tags['content']) if type(tags['content']) in [dict, list] else tags['content']        
    elif type(tags) is list:
        for tag in tags:
            key = f'{context}.{tag["tagname"]}' if len(context) > 0 else tag['tagname']
            obj[key] = processTags(tag['content']) if type(tag['content']) is dict or type(tag['content']) is list else tag['content']
            
            attributes = extractAttributes(tag['attributes'])
            for attributekey in attributes.keys():
                obj[tag["tagname"]][attributekey] = attributes[attributekey]
    return obj
  
def indent(string, level):
    return 2*level*' ' + string

def replacevalue(value):
    if value == '""' or len(value) == 0:
        return 'null'
      
    if value in replacers:
        newValue = replacers[value]
        if isinstance(newValue, types.FunctionType):
            value = newValue()
        else:
            value = newValue
    return f'"{value}"' if value != 'null' else value

def postprocesscontent(processed, rootindent=0):
    indent_ = rootindent
    lines = []

    if rootindent == 0:
        lines.append( indent('{', rootindent) )
    for key in processed.keys():
        formattedkey = f'"{key}"'
        value = processed[key]
        if type(value) is str:
            value = replacevalue(value)
            lines.append( indent( f'{formattedkey}: {value},', indent_ ) )
        else:
            lines.append( indent(f'{formattedkey}: '+'{', indent_) )
            embeddedobject = postprocesscontent(processed[key], indent_+1)
            for e in embeddedobject:
                lines.append(e)
    lines[-1] = lines[-1][:-1]
    lines.append( indent('},' if rootindent > 0 else '}', rootindent) )    
    return lines

#-----------------------------------------------------#

# End of function definitions and start of processing #

#-----------------------------------------------------#

content = extractContent(filename)
tags = getTag(content)['content']
processed = processTags(tags)
postprocessed = '\n'.join( postprocesscontent(processed) )

filename = filename.split('.')[0]
jsonfile = open(f'{filename}.json', 'w')
jsonfile.write(postprocessed)
jsonfile.close()

