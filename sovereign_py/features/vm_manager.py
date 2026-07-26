"""
Virtual Machine Management for ML Filesystem v1.8+

Supports:
- Docker containers (lightweight, fast)
- QEMU/KVM VMs (full OS support)
- Web-based access (VNC/noVNC)
- Snapshot management
- Resource control
"""

import docker
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import json

from core.database import db
from core.enhanced_models import VMConfiguration, VMSnapshot
from core.config import Config
from core.exceptions import MLFilesystemException


class VMManager:
    """
    Manages virtual machines and containers.
    """
    
    def __init__(self):
        self.vm_root = Config.SANDBOX_ROOT / 'vms'
        self.vm_root.mkdir(parents=True, exist_ok=True)
        
        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            self.docker_available = True
        except:
            self.docker_available = False
            print("⚠️  Docker not available")
    
    def create_vm(
        self,
        name: str,
        vm_type: str,
        image: str,
        owner_id: int,
        description: str = None,
        os_type: str = 'linux',
        cpu_cores: int = 2,
        memory_mb: int = 2048,
        disk_gb: int = 20,
        network_mode: str = 'bridge',
        port_mappings: Dict = None,
        config: Dict = None
    ) -> VMConfiguration:
        """
        Create a new VM configuration.
        
        Args:
            name: VM name
            vm_type: 'docker', 'qemu', or 'virtualbox'
            image: Docker image or VM image path
            owner_id: User ID
            description: VM description
            os_type: Operating system type
            cpu_cores: Number of CPU cores
            memory_mb: Memory in MB
            disk_gb: Disk size in GB
            network_mode: Network mode
            port_mappings: Port mappings {guest: host}
            config: Additional configuration
            
        Returns:
            Created VMConfiguration
        """
        session = db.get_session()
        try:
            vm_config = VMConfiguration(
                name=name,
                description=description,
                vm_type=vm_type,
                image=image,
                os_type=os_type,
                cpu_cores=cpu_cores,
                memory_mb=memory_mb,
                disk_gb=disk_gb,
                network_mode=network_mode,
                port_mappings=port_mappings or {},
                config=config or {},
                status='stopped',
                enabled=True,
                owner_id=owner_id
            )
            
            session.add(vm_config)
            session.commit()
            session.refresh(vm_config)
            
            print(f"✓ Created VM: {name} ({vm_type})")
            return vm_config
        finally:
            session.close()
    
    def list_vms(self, owner_id: int = None, vm_type: str = None) -> List[VMConfiguration]:
        """List VM configurations."""
        session = db.get_session()
        try:
            query = session.query(VMConfiguration)
            
            if owner_id:
                query = query.filter_by(owner_id=owner_id)
            if vm_type:
                query = query.filter_by(vm_type=vm_type)
            
            return query.all()
        finally:
            session.close()
    
    def start_vm(self, vm_id: int) -> Dict[str, Any]:
        """
        Start a VM.
        
        Returns:
            Status information
        """
        session = db.get_session()
        try:
            vm = session.query(VMConfiguration).filter_by(id=vm_id).first()
            if not vm:
                return {'error': 'VM not found'}
            
            if not vm.enabled:
                return {'error': 'VM is disabled'}
            
            if vm.vm_type == 'docker':
                result = self._start_docker_container(vm)
            elif vm.vm_type == 'qemu':
                result = self._start_qemu_vm(vm)
            else:
                result = {'error': f'Unsupported VM type: {vm.vm_type}'}
            
            if result.get('success'):
                vm.status = 'running'
                vm.last_started = datetime.utcnow()
                session.commit()
            
            return result
        finally:
            session.close()
    
    def _start_docker_container(self, vm: VMConfiguration) -> Dict[str, Any]:
        """Start Docker container."""
        if not self.docker_available:
            return {'error': 'Docker not available'}
        
        try:
            # Pull image if needed
            try:
                self.docker_client.images.get(vm.image)
            except docker.errors.ImageNotFound:
                print(f"Pulling image: {vm.image}")
                self.docker_client.images.pull(vm.image)
            
            # Prepare port bindings
            port_bindings = {}
            for guest_port, host_port in vm.port_mappings.items():
                port_bindings[f'{guest_port}/tcp'] = host_port
            
            # Start container
            container = self.docker_client.containers.run(
                vm.image,
                name=f'mlfs_vm_{vm.id}',
                detach=True,
                ports=port_bindings,
                network_mode=vm.network_mode,
                mem_limit=f'{vm.memory_mb}m',
                cpu_count=vm.cpu_cores,
                **vm.config
            )
            
            return {
                'success': True,
                'container_id': container.id,
                'name': container.name,
                'status': container.status,
                'ports': port_bindings
            }
        
        except Exception as e:
            return {'error': f'Failed to start container: {str(e)}'}
    
    def _start_qemu_vm(self, vm: VMConfiguration) -> Dict[str, Any]:
        """Start QEMU VM."""
        try:
            # Create VM directory
            vm_dir = self.vm_root / f'vm_{vm.id}'
            vm_dir.mkdir(parents=True, exist_ok=True)
            
            # Build QEMU command
            cmd = [
                'qemu-system-x86_64',
                '-m', str(vm.memory_mb),
                '-smp', str(vm.cpu_cores),
                '-hda', str(vm_dir / 'disk.qcow2'),
                '-cdrom', vm.image,
                '-boot', 'd',
                '-vnc', f':{vm.id}',  # VNC on port 5900 + vm.id
                '-daemonize'
            ]
            
            # Add port forwarding
            for guest_port, host_port in vm.port_mappings.items():
                cmd.extend(['-netdev', f'user,id=net0,hostfwd=tcp::{host_port}-:{guest_port}'])
            
            # Run QEMU
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'vnc_port': 5900 + vm.id,
                    'message': 'QEMU VM started'
                }
            else:
                return {'error': f'QEMU failed: {result.stderr}'}
        
        except Exception as e:
            return {'error': f'Failed to start QEMU: {str(e)}'}
    
    def stop_vm(self, vm_id: int) -> Dict[str, Any]:
        """Stop a VM."""
        session = db.get_session()
        try:
            vm = session.query(VMConfiguration).filter_by(id=vm_id).first()
            if not vm:
                return {'error': 'VM not found'}
            
            if vm.vm_type == 'docker':
                result = self._stop_docker_container(vm)
            elif vm.vm_type == 'qemu':
                result = self._stop_qemu_vm(vm)
            else:
                result = {'error': f'Unsupported VM type: {vm.vm_type}'}
            
            if result.get('success'):
                vm.status = 'stopped'
                vm.last_stopped = datetime.utcnow()
                session.commit()
            
            return result
        finally:
            session.close()
    
    def _stop_docker_container(self, vm: VMConfiguration) -> Dict[str, Any]:
        """Stop Docker container."""
        if not self.docker_available:
            return {'error': 'Docker not available'}
        
        try:
            container_name = f'mlfs_vm_{vm.id}'
            container = self.docker_client.containers.get(container_name)
            container.stop()
            container.remove()
            
            return {'success': True, 'message': 'Container stopped'}
        except docker.errors.NotFound:
            return {'success': True, 'message': 'Container not running'}
        except Exception as e:
            return {'error': f'Failed to stop container: {str(e)}'}
    
    def _stop_qemu_vm(self, vm: VMConfiguration) -> Dict[str, Any]:
        """Stop QEMU VM."""
        try:
            # Find QEMU process
            result = subprocess.run(
                ['pgrep', '-f', f'qemu.*vm_{vm.id}'],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                pid = result.stdout.strip()
                subprocess.run(['kill', pid])
                return {'success': True, 'message': 'QEMU VM stopped'}
            
            return {'success': True, 'message': 'VM not running'}
        except Exception as e:
            return {'error': f'Failed to stop QEMU: {str(e)}'}
    
    def get_vm_status(self, vm_id: int) -> Dict[str, Any]:
        """Get current VM status."""
        session = db.get_session()
        try:
            vm = session.query(VMConfiguration).filter_by(id=vm_id).first()
            if not vm:
                return {'error': 'VM not found'}
            
            if vm.vm_type == 'docker':
                return self._get_docker_status(vm)
            elif vm.vm_type == 'qemu':
                return self._get_qemu_status(vm)
            else:
                return vm.to_dict()
        finally:
            session.close()
    
    def _get_docker_status(self, vm: VMConfiguration) -> Dict[str, Any]:
        """Get Docker container status."""
        if not self.docker_available:
            return {**vm.to_dict(), 'runtime_status': 'docker_unavailable'}
        
        try:
            container_name = f'mlfs_vm_{vm.id}'
            container = self.docker_client.containers.get(container_name)
            
            return {
                **vm.to_dict(),
                'runtime_status': container.status,
                'container_id': container.id,
                'ports': container.ports
            }
        except docker.errors.NotFound:
            return {**vm.to_dict(), 'runtime_status': 'not_running'}
        except Exception as e:
            return {**vm.to_dict(), 'runtime_status': 'error', 'error': str(e)}
    
    def _get_qemu_status(self, vm: VMConfiguration) -> Dict[str, Any]:
        """Get QEMU VM status."""
        try:
            result = subprocess.run(
                ['pgrep', '-f', f'qemu.*vm_{vm.id}'],
                capture_output=True,
                text=True
            )
            
            runtime_status = 'running' if result.stdout else 'not_running'
            return {**vm.to_dict(), 'runtime_status': runtime_status}
        except:
            return {**vm.to_dict(), 'runtime_status': 'unknown'}
    
    def create_snapshot(self, vm_id: int, name: str, description: str = None) -> Optional[VMSnapshot]:
        """Create a VM snapshot."""
        session = db.get_session()
        try:
            vm = session.query(VMConfiguration).filter_by(id=vm_id).first()
            if not vm:
                return None
            
            # Only Docker supports snapshots easily
            if vm.vm_type == 'docker' and self.docker_available:
                try:
                    container_name = f'mlfs_vm_{vm.id}'
                    container = self.docker_client.containers.get(container_name)
                    
                    # Commit container to new image
                    snapshot_image = container.commit(
                        repository=f'mlfs_snapshot_{vm.id}',
                        tag=name
                    )
                    
                    snapshot = VMSnapshot(
                        vm_id=vm.id,
                        name=name,
                        description=description,
                        snapshot_path=f'{snapshot_image.id}',
                        size_mb=0  # Would need to calculate
                    )
                    
                    session.add(snapshot)
                    session.commit()
                    session.refresh(snapshot)
                    
                    print(f"✓ Created snapshot: {name}")
                    return snapshot
                except Exception as e:
                    print(f"✗ Snapshot failed: {e}")
                    return None
            
            return None
        finally:
            session.close()
    
    def list_snapshots(self, vm_id: int) -> List[VMSnapshot]:
        """List snapshots for a VM."""
        session = db.get_session()
        try:
            return session.query(VMSnapshot).filter_by(vm_id=vm_id).all()
        finally:
            session.close()
    
    def restore_snapshot(self, snapshot_id: int) -> bool:
        """Restore VM from snapshot."""
        # Implementation would restore VM to snapshot state
        # For Docker: restart container from snapshot image
        # For QEMU: restore disk image from snapshot
        pass
    
    def delete_vm(self, vm_id: int) -> bool:
        """Delete a VM configuration."""
        session = db.get_session()
        try:
            vm = session.query(VMConfiguration).filter_by(id=vm_id).first()
            if not vm:
                return False
            
            # Stop VM if running
            self.stop_vm(vm_id)
            
            # Delete VM directory
            vm_dir = self.vm_root / f'vm_{vm.id}'
            if vm_dir.exists():
                import shutil
                shutil.rmtree(vm_dir)
            
            # Delete database record
            session.delete(vm)
            session.commit()
            
            print(f"✓ Deleted VM: {vm.name}")
            return True
        finally:
            session.close()
