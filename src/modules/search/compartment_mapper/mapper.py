import datetime as dt
import logging

from oci import Signer
from oci import pagination
from oci.identity import IdentityClient

class Compartment:
    def __init__(self, id: str, name: str, parent: str):
        self.id = id
        self.name = name
        self.parent = parent

    def __str__(self) -> str:
        return self.id
    
    def __repr__(self) -> str:
        return (f'{self.id}\n'
                f'\t{self.name}\n'
                f'\t{self.parent}\n')

    @property
    def has_parent(self) -> bool:
        if self.parent:
            return True
        
        return False


class CompartmentMapper:
    '''CompartmentMapper contains an updatable, in-memory list of compartments in the
        tenancy.
    '''

    NOT_FOUND = 'Compartment Not Found'

    def __init__(self,
        config: dict[str, str],
        signer: Signer | None,
        logger: logging.Logger=logging.getLogger(__name__)):

        self.logger = logger
        self.client: IdentityClient = IdentityClient(config, signer=signer)
        self.tenancy: str = config['tenancy']

        # compartments keep a dict mapping compartment OCIDs to compartment definitions
        self.compartments: dict[str, Compartment] = {}
        self._load_compartments(init=True)
        self.last_load = dt.datetime.now()

    def refresh_compartments(self, force: bool=False) -> None:
        now = dt.datetime.now()
        if (self.last_load + dt.timedelta(minutes=5)) < now or force:
            self._load_compartments()
            self.last_load = now

    def update_compartment(self, id: str, update: Compartment):
        self.logger.debug(f'updating compartment {id}')
        self.compartments.update({id: update})

    def get_compartment_path(self, id: str) -> str:
        self.refresh_compartments()
        path = ''

        cmp = self.compartments.get(id)
        if not cmp:
            return self.NOT_FOUND
        
        if cmp.has_parent:
            path = self.get_compartment_path(cmp.parent)

        path = f'{path}/{cmp.name}'
        
        return path

    def _load_compartments(self, init: bool=False) -> None:
        self.logger.info('Loading compartments')

        if init:
        # Start with root compartment on first run
            response = self.client.get_compartment(self.tenancy)
            if response.status != 200:
                self.logger.error(f'non-2XX response loading compartments: {response.status}')
                return
            
            self.update_compartment(response.data.id, Compartment(response.data.id,
                                                            response.data.name,
                                                            ''))

        # Get and process all remaining compartments
        response = pagination.list_call_get_all_results(self.client.list_compartments,
                        self.tenancy,
                        compartment_id_in_subtree=True,
                        limit=1000)
        if response.status != 200:
            self.logger.error(f'non-2XX response loading compartments: {response.status}')
            return
        
        self.logger.info(f'Found {len(response.data)} compartments')
        for compartment in response.data:
            self.update_compartment(compartment.id, Compartment(compartment.id,
                                                                compartment.name,
                                                                compartment.compartment_id))

        self.logger.info('All compartments loaded')
