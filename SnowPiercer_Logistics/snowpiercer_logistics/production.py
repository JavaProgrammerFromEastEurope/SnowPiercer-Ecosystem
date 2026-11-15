"""Witness-backed admission; experimental only, NOT a production certification."""
from .secure import SecureLogisticsService, AdmissionError
from .witness import witness_request

class WitnessBackedLogisticsService(SecureLogisticsService):
    def __init__(self,root,uid_roles,witness_socket,*,timeout=2.0):
        super().__init__(root,uid_roles,timeout=timeout)
        self.witness_socket=str(witness_socket)

    def _read_witness(self):
        return witness_request(self.witness_socket,'read',timeout=self.timeout)

    def _read_anchor(self):
        local=super()._read_anchor()
        remote=self._read_witness()
        if local!=remote:
            raise AdmissionError('local checkpoint / independent witness mismatch')
        return local

    def _write_anchor(self,value):
        # Witness CAS is the linearization point. A crash between CAS and local
        # checkpoint update is quarantined on restart; no unsafe automatic repair.
        local=super()._read_anchor()
        witness_request(self.witness_socket,'cas',before=local,after=value,timeout=self.timeout)
        super()._write_anchor(value)

    def _admit(self):
        # An absent witness is never silently replaced by a local genesis.
        self._read_witness()
        super()._admit()
