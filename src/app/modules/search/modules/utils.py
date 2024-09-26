#!/usr/bin/python3.11

# URL prefixes by service
url_map = {
    'Instance': 'compute/instances/',
    'Volume': 'block-storage/volumes/',
    'Bucket': 'object-storage/buckets/' # TODO Buckets special case
}

# Return a formatted URL for the resource or None
def construct_url(resource: dict, region: str) -> str | None:
    try:
        return (f'https://cloud.oracle.com/{url_map[resource["resource_type"]]}'
                f'{resource["identifier"]}?region={region}')
    except KeyError:
        return None

if __name__ == '__main__':
    pass