"""
ML Filesystem - ML Agent System
Implements intelligent ML agents for file organization, learning, and analysis.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np
from models import MLAgent, File, FileChain, ActivityLog, Database


class MLAgentSystem:
    """
    ML Agent System for intelligent file operations.
    Supports organization, learning, and custom agent behaviors.
    """
    
    def __init__(self, db: Database = None, api_key: str = None):
        """
        Initialize ML agent system.
        
        Args:
            db: Database instance
            api_key: Anthropic API key
        """
        self.db = db or Database()
        
        # Initialize Anthropic client
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            print("Warning: No Anthropic API key provided. ML features will be limited.")
        
        # Initialize ChromaDB for vector storage
        self.chroma_client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory="./chroma_db"
        ))
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
    def create_agent(self, name: str, description: str, agent_type: str,
                    user_id: int, system_prompt: str = None,
                    config: Dict = None) -> MLAgent:
        """
        Create a new ML agent.
        
        Args:
            name: Agent name
            description: Agent description
            agent_type: Type of agent (organizer, learner, analyzer, custom)
            user_id: Owner user ID
            system_prompt: Custom system prompt
            config: Agent configuration
            
        Returns:
            Created MLAgent object
        """
        session = self.db.get_session()
        
        try:
            # Create embeddings collection for this agent
            collection_name = f"agent_{name.lower().replace(' ', '_')}_{user_id}"
            
            try:
                collection = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={"agent_type": agent_type}
                )
            except:
                collection = self.chroma_client.get_collection(name=collection_name)
            
            # Default system prompts by type
            default_prompts = {
                'organizer': """You are an intelligent file organizer. Your role is to:
1. Analyze file content, metadata, and relationships
2. Suggest optimal folder structures and categorizations
3. Identify duplicate or similar files
4. Recommend tags and organizational strategies
5. Detect patterns in file usage and access

Be concise, practical, and actionable in your suggestions.""",
                
                'learner': """You are a knowledge extraction and learning system. Your role is to:
1. Read and comprehend content from files and file chains
2. Extract key concepts, facts, and relationships
3. Build a structured knowledge base
4. Generate summaries and insights
5. Answer questions based on learned information

Be thorough, accurate, and make connections between different pieces of information.""",
                
                'analyzer': """You are a file and content analyzer. Your role is to:
1. Analyze file content for patterns and insights
2. Detect data quality issues
3. Identify relationships between files
4. Generate metadata and descriptions
5. Provide statistical and qualitative analysis

Be detailed, objective, and data-driven in your analysis."""
            }
            
            agent = MLAgent(
                name=name,
                description=description,
                agent_type=agent_type,
                system_prompt=system_prompt or default_prompts.get(agent_type, ''),
                owner_id=user_id,
                config=config or {},
                embeddings_collection=collection_name
            )
            
            session.add(agent)
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                ml_agent_id=agent.id,
                action='create_agent',
                details={'name': name, 'type': agent_type}
            )
            session.add(log)
            
            session.commit()
            return agent
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def _call_claude(self, system_prompt: str, user_message: str,
                    model: str = 'claude-sonnet-4-20250514') -> str:
        """
        Call Claude API.
        
        Args:
            system_prompt: System prompt
            user_message: User message
            model: Model to use
            
        Returns:
            Claude's response
        """
        if not self.client:
            return "Error: Anthropic API not configured. Please set ANTHROPIC_API_KEY."
        
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"Error calling Claude API: {str(e)}"
    
    def organize_files(self, agent_id: int, file_ids: List[int],
                      user_id: int) -> Dict[str, Any]:
        """
        Use an organizer agent to analyze and suggest file organization.
        
        Args:
            agent_id: ML agent ID
            file_ids: List of file IDs to organize
            user_id: User ID
            
        Returns:
            Organization suggestions
        """
        session = self.db.get_session()
        
        try:
            agent = session.query(MLAgent).filter_by(id=agent_id).first()
            if not agent or agent.agent_type != 'organizer':
                raise ValueError("Invalid organizer agent")
            
            # Get file information
            files = session.query(File).filter(File.id.in_(file_ids)).all()
            
            if not files:
                return {'error': 'No files found'}
            
            # Prepare file information for Claude
            file_info = []
            for file in files:
                info = {
                    'name': file.name,
                    'path': file.path,
                    'type': file.file_type,
                    'size': file.size,
                    'tags': [tag.name for tag in file.tags],
                    'created': file.created_at.isoformat() if file.created_at else None,
                    'modified': file.modified_at.isoformat() if file.modified_at else None
                }
                
                # Include content preview for text files
                if file.content and len(file.content) < 5000:
                    info['content_preview'] = file.content[:500]
                
                file_info.append(info)
            
            # Create prompt
            user_message = f"""Analyze these {len(files)} files and provide organization suggestions:

Files:
{json.dumps(file_info, indent=2)}

Please provide:
1. Suggested folder structure
2. Recommended tags for each file
3. Identified duplicates or similar files
4. Any patterns or insights
5. Actionable next steps

Format your response as JSON with keys: folder_structure, file_tags, duplicates, insights, actions"""
            
            # Call Claude
            response = self._call_claude(agent.system_prompt, user_message, agent.model)
            
            # Update agent statistics
            agent.interactions_count += 1
            agent.files_processed += len(files)
            agent.last_active = datetime.utcnow()
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                ml_agent_id=agent_id,
                action='organize_files',
                details={'file_count': len(files), 'response_length': len(response)}
            )
            session.add(log)
            
            session.commit()
            
            # Try to parse JSON response
            try:
                suggestions = json.loads(response)
            except:
                # If not JSON, return as text
                suggestions = {'raw_response': response}
            
            return suggestions
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def learn_from_files(self, agent_id: int, file_ids: List[int],
                        user_id: int) -> Dict[str, Any]:
        """
        Use a learner agent to extract knowledge from files.
        
        Args:
            agent_id: ML agent ID
            file_ids: List of file IDs to learn from
            user_id: User ID
            
        Returns:
            Learning results with extracted knowledge
        """
        session = self.db.get_session()
        
        try:
            agent = session.query(MLAgent).filter_by(id=agent_id).first()
            if not agent or agent.agent_type != 'learner':
                raise ValueError("Invalid learner agent")
            
            # Get files
            files = session.query(File).filter(File.id.in_(file_ids)).all()
            
            if not files:
                return {'error': 'No files found'}
            
            # Get agent's collection
            collection = self.chroma_client.get_collection(name=agent.embeddings_collection)
            
            # Process each file
            learned_items = []
            
            for file in files:
                if file.is_directory or not file.content:
                    continue
                
                # Generate embeddings
                text_chunks = self._chunk_text(file.content)
                
                for i, chunk in enumerate(text_chunks):
                    # Create embedding
                    embedding = self.embedding_model.encode(chunk).tolist()
                    
                    # Store in ChromaDB
                    doc_id = f"file_{file.id}_chunk_{i}"
                    collection.add(
                        embeddings=[embedding],
                        documents=[chunk],
                        metadatas=[{
                            'file_id': file.id,
                            'file_name': file.name,
                            'chunk_index': i,
                            'timestamp': datetime.utcnow().isoformat()
                        }],
                        ids=[doc_id]
                    )
                
                # Extract key concepts using Claude
                user_message = f"""Analyze this file and extract key information:

File: {file.name}
Type: {file.file_type}
Content:
{file.content[:4000]}

Please provide:
1. Main topics and concepts
2. Key facts and data points
3. Important relationships or connections
4. Summary in 2-3 sentences

Format as JSON with keys: topics, facts, relationships, summary"""
                
                response = self._call_claude(agent.system_prompt, user_message, agent.model)
                
                try:
                    extracted = json.loads(response)
                except:
                    extracted = {'raw_response': response}
                
                learned_items.append({
                    'file_id': file.id,
                    'file_name': file.name,
                    'extracted': extracted
                })
                
                # Mark file as processed
                file.ml_metadata['learned_by'] = file.ml_metadata.get('learned_by', [])
                if agent_id not in file.ml_metadata['learned_by']:
                    file.ml_metadata['learned_by'].append(agent_id)
            
            # Update agent knowledge base
            if not agent.knowledge_base:
                agent.knowledge_base = {}
            
            agent.knowledge_base['learned_files'] = agent.knowledge_base.get('learned_files', [])
            agent.knowledge_base['learned_files'].extend(file_ids)
            agent.knowledge_base['last_learning'] = datetime.utcnow().isoformat()
            
            # Update statistics
            agent.interactions_count += 1
            agent.files_processed += len(files)
            agent.last_active = datetime.utcnow()
            agent.is_learning = False
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                ml_agent_id=agent_id,
                action='learn_from_files',
                details={'file_count': len(files), 'chunks_processed': sum(len(self._chunk_text(f.content)) for f in files if f.content)}
            )
            session.add(log)
            
            session.commit()
            
            return {
                'success': True,
                'files_processed': len(files),
                'learned_items': learned_items
            }
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def query_agent_knowledge(self, agent_id: int, query: str,
                             user_id: int, top_k: int = 5) -> Dict[str, Any]:
        """
        Query an agent's learned knowledge.
        
        Args:
            agent_id: ML agent ID
            query: Query string
            user_id: User ID
            top_k: Number of results to return
            
        Returns:
            Query results with relevant information
        """
        session = self.db.get_session()
        
        try:
            agent = session.query(MLAgent).filter_by(id=agent_id).first()
            if not agent:
                raise ValueError("Agent not found")
            
            # Get agent's collection
            collection = self.chroma_client.get_collection(name=agent.embeddings_collection)
            
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Search in ChromaDB
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            
            # Prepare context from retrieved documents
            context_docs = []
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i]
                context_docs.append({
                    'content': doc,
                    'file_name': metadata.get('file_name'),
                    'file_id': metadata.get('file_id'),
                    'relevance': 1 - results['distances'][0][i]  # Convert distance to similarity
                })
            
            # Generate response using Claude
            context_text = "\n\n".join([
                f"[From {doc['file_name']}]\n{doc['content']}"
                for doc in context_docs
            ])
            
            user_message = f"""Based on the following information from learned files, answer this query:

Query: {query}

Relevant Information:
{context_text}

Please provide a comprehensive answer based on the information above. If the information is insufficient, say so."""
            
            response = self._call_claude(agent.system_prompt, user_message, agent.model)
            
            # Update statistics
            agent.interactions_count += 1
            agent.last_active = datetime.utcnow()
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                ml_agent_id=agent_id,
                action='query_knowledge',
                details={'query': query, 'results_count': len(context_docs)}
            )
            session.add(log)
            
            session.commit()
            
            return {
                'answer': response,
                'sources': context_docs,
                'agent_name': agent.name
            }
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def analyze_file_chain(self, agent_id: int, file_chain_id: int,
                          user_id: int) -> Dict[str, Any]:
        """
        Analyze a file chain with an ML agent.
        
        Args:
            agent_id: ML agent ID
            file_chain_id: File chain ID
            user_id: User ID
            
        Returns:
            Analysis results
        """
        session = self.db.get_session()
        
        try:
            agent = session.query(MLAgent).filter_by(id=agent_id).first()
            file_chain = session.query(FileChain).filter_by(id=file_chain_id).first()
            
            if not agent or not file_chain:
                raise ValueError("Agent or file chain not found")
            
            # Get chain files in order
            files = file_chain.files
            
            # Prepare chain information
            chain_info = {
                'name': file_chain.name,
                'description': file_chain.description,
                'file_count': len(files),
                'files': []
            }
            
            for file in files:
                file_data = {
                    'name': file.name,
                    'type': file.file_type,
                    'path': file.path
                }
                
                if file.content and len(file.content) < 3000:
                    file_data['content'] = file.content
                elif file.content:
                    file_data['content_preview'] = file.content[:500]
                
                chain_info['files'].append(file_data)
            
            # Generate analysis
            user_message = f"""Analyze this file chain and provide insights:

Chain Name: {file_chain.name}
Description: {file_chain.description}

Files in Chain:
{json.dumps(chain_info['files'], indent=2)}

Please provide:
1. Overall analysis of the file chain
2. Relationships and dependencies between files
3. Key themes or patterns
4. Recommendations for organization or improvements
5. Potential use cases or applications

Format as JSON with keys: analysis, relationships, themes, recommendations, use_cases"""
            
            response = self._call_claude(agent.system_prompt, user_message, agent.model)
            
            # Update statistics
            agent.interactions_count += 1
            agent.files_processed += len(files)
            agent.last_active = datetime.utcnow()
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                ml_agent_id=agent_id,
                action='analyze_file_chain',
                details={'file_chain_id': file_chain_id, 'file_count': len(files)}
            )
            session.add(log)
            
            session.commit()
            
            try:
                analysis = json.loads(response)
            except:
                analysis = {'raw_response': response}
            
            return analysis
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def _chunk_text(self, text: str, chunk_size: int = 500,
                   overlap: int = 50) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > chunk_size * 0.5:  # Only break if past halfway
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1
            
            chunks.append(chunk.strip())
            start = end - overlap
        
        return chunks
    
    def auto_organize_by_similarity(self, user_id: int,
                                   directory_path: str = '/') -> Dict[str, Any]:
        """
        Automatically organize files by semantic similarity.
        
        Args:
            user_id: User ID
            directory_path: Directory to organize
            
        Returns:
            Organization suggestions
        """
        session = self.db.get_session()
        
        try:
            # Get all files in directory
            parent = session.query(File).filter_by(
                path=directory_path,
                is_directory=True,
                owner_id=user_id
            ).first()
            
            if not parent:
                return {'error': 'Directory not found'}
            
            files = session.query(File).filter_by(
                parent_id=parent.id,
                is_directory=False
            ).all()
            
            if not files:
                return {'message': 'No files to organize'}
            
            # Generate embeddings for all files
            file_embeddings = []
            file_data = []
            
            for file in files:
                if not file.content:
                    continue
                
                # Get first chunk as representative
                chunks = self._chunk_text(file.content)
                if chunks:
                    embedding = self.embedding_model.encode(chunks[0])
                    file_embeddings.append(embedding)
                    file_data.append({
                        'id': file.id,
                        'name': file.name,
                        'type': file.file_type
                    })
            
            if len(file_embeddings) < 2:
                return {'message': 'Not enough files with content to organize'}
            
            # Perform clustering
            from sklearn.cluster import KMeans
            
            n_clusters = min(5, len(file_embeddings))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            clusters = kmeans.fit_predict(file_embeddings)
            
            # Group files by cluster
            clustered_files = {}
            for i, cluster_id in enumerate(clusters):
                if cluster_id not in clustered_files:
                    clustered_files[cluster_id] = []
                clustered_files[cluster_id].append(file_data[i])
            
            # Generate cluster names/themes
            suggestions = {
                'clusters': [],
                'organization_plan': []
            }
            
            for cluster_id, cluster_files in clustered_files.items():
                cluster_info = {
                    'cluster_id': cluster_id,
                    'file_count': len(cluster_files),
                    'files': cluster_files,
                    'suggested_folder': f'Group_{cluster_id + 1}'
                }
                suggestions['clusters'].append(cluster_info)
            
            return suggestions
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()


if __name__ == '__main__':
    # Test ML agent system
    db = Database()
    db.create_all()
    db.init_default_data()
    
    ml_system = MLAgentSystem(db=db)
    
    print("ML Agent System initialized successfully!")
    
    # Test agent creation
    session = db.get_session()
    user = session.query(User).first()
    session.close()
    
    if user:
        try:
            agent = ml_system.create_agent(
                name='Test Organizer',
                description='Test agent for organizing files',
                agent_type='organizer',
                user_id=user.id
            )
            print(f"Created agent: {agent.name}")
        except Exception as e:
            print(f"Test failed: {e}")
