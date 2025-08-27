"""
Stream Parser for AgentCore runtime streaming responses.

This module provides utilities to parse and process streaming events from
AgentCore runtimes, converting the JSON lines format into structured events
for analysis and testing.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Generator, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class StreamEventType(Enum):
    """Event types from AgentCore runtime streaming responses."""
    INPUT_CAPTURE = "input_capture"
    THOUGHT_CAPTURE = "thought_capture" 
    TOOL_EXECUTION = "tool_execution"
    AGENT_SWITCH = "agent_switch"
    OUTPUT_CAPTURE = "output_capture"
    ERROR = "error"
    DONE = "done"
    RAW_TEXT = "raw_text"
    UNKNOWN = "unknown"

class StreamEvent:
    """Represents a single streaming event from an AgentCore runtime."""
    
    def __init__(self, event_data: Dict[str, Any]):
        """Initialize a stream event from raw event data.
        
        Args:
            event_data: Raw event data from the streaming response
        """
        self.raw_data = event_data
        self.event_type = self._parse_event_type(event_data)
        self.timestamp = self._parse_timestamp(event_data)
        self.session_id = event_data.get('session_id')
        self.data = event_data.get('data', {})
        self.metadata = event_data.get('metadata', {})
    
    def _parse_event_type(self, event_data: Dict[str, Any]) -> StreamEventType:
        """Parse the event type from raw event data."""
        event_str = event_data.get('event', '').lower()
        
        # Map event strings to enum values
        event_mapping = {
            'input_capture': StreamEventType.INPUT_CAPTURE,
            'thought_capture': StreamEventType.THOUGHT_CAPTURE,
            'tool_execution': StreamEventType.TOOL_EXECUTION,
            'agent_switch': StreamEventType.AGENT_SWITCH,
            'output_capture': StreamEventType.OUTPUT_CAPTURE,
            'error': StreamEventType.ERROR,
            'done': StreamEventType.DONE,
            'raw_text': StreamEventType.RAW_TEXT
        }
        
        return event_mapping.get(event_str, StreamEventType.UNKNOWN)
    
    def _parse_timestamp(self, event_data: Dict[str, Any]) -> Optional[datetime]:
        """Parse timestamp from event data."""
        timestamp_str = event_data.get('timestamp')
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        return None
    
    def is_input_event(self) -> bool:
        """Check if this is an input capture event."""
        return self.event_type == StreamEventType.INPUT_CAPTURE
    
    def is_thought_event(self) -> bool:
        """Check if this is a thought capture event."""
        return self.event_type == StreamEventType.THOUGHT_CAPTURE
    
    def is_tool_event(self) -> bool:
        """Check if this is a tool execution event."""
        return self.event_type == StreamEventType.TOOL_EXECUTION
    
    def is_output_event(self) -> bool:
        """Check if this is an output capture event."""
        return self.event_type == StreamEventType.OUTPUT_CAPTURE
    
    def is_error_event(self) -> bool:
        """Check if this is an error event."""
        return self.event_type == StreamEventType.ERROR
    
    def is_done_event(self) -> bool:
        """Check if this is a completion event."""
        return self.event_type == StreamEventType.DONE
    
    def get_content(self) -> Optional[str]:
        """Extract the main content from the event."""
        if self.is_input_event():
            return self.data.get('prompt') or self.data.get('content')
        elif self.is_thought_event():
            return self.data.get('thinking') or self.data.get('content')
        elif self.is_tool_event():
            return self.data.get('tool_info') or self.data.get('content')
        elif self.is_output_event():
            return self.data.get('content')
        elif self.is_error_event():
            return self.data.get('error')
        elif self.event_type == StreamEventType.RAW_TEXT:
            return self.data.get('text')
        return None
    
    def get_agent_name(self) -> Optional[str]:
        """Extract the agent name if available."""
        return self.data.get('agent') or self.metadata.get('agent')
    
    def __str__(self) -> str:
        """String representation of the stream event."""
        content = self.get_content() or ""
        content_preview = content[:50] + "..." if len(content) > 50 else content
        
        return f"StreamEvent({self.event_type.value}, content='{content_preview}')"
    
    def __repr__(self) -> str:
        """Detailed representation of the stream event."""
        return f"StreamEvent(type={self.event_type.value}, session_id={self.session_id}, timestamp={self.timestamp})"

class StreamParser:
    """Parser for AgentCore runtime streaming responses."""
    
    def __init__(self):
        """Initialize the stream parser."""
        self.events: List[StreamEvent] = []
        self.session_events: Dict[str, List[StreamEvent]] = {}
    
    def parse_events(self, events_data: List[Dict[str, Any]]) -> List[StreamEvent]:
        """Parse a list of raw event data into StreamEvent objects.
        
        Args:
            events_data: List of raw event dictionaries
            
        Returns:
            List of parsed StreamEvent objects
        """
        parsed_events = []
        
        for event_data in events_data:
            try:
                event = StreamEvent(event_data)
                parsed_events.append(event)
                
                # Group by session
                if event.session_id:
                    if event.session_id not in self.session_events:
                        self.session_events[event.session_id] = []
                    self.session_events[event.session_id].append(event)
                    
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}, raw_data: {event_data}")
                # Create an error event for unparseable data
                error_event = StreamEvent({
                    "event": "error",
                    "data": {"error": f"Parse error: {str(e)}", "raw_data": event_data},
                    "timestamp": datetime.now().isoformat()
                })
                parsed_events.append(error_event)
        
        self.events.extend(parsed_events)
        return parsed_events
    
    def get_events_by_type(self, event_type: StreamEventType) -> List[StreamEvent]:
        """Get all events of a specific type.
        
        Args:
            event_type: The type of events to retrieve
            
        Returns:
            List of events matching the specified type
        """
        return [event for event in self.events if event.event_type == event_type]
    
    def get_events_by_session(self, session_id: str) -> List[StreamEvent]:
        """Get all events for a specific session.
        
        Args:
            session_id: Session ID to filter by
            
        Returns:
            List of events for the specified session
        """
        return self.session_events.get(session_id, [])
    
    def get_conversation_flow(self, session_id: Optional[str] = None) -> List[Tuple[str, str]]:
        """Extract the conversation flow from events.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            List of (event_type, content) tuples showing the conversation flow
        """
        events = self.get_events_by_session(session_id) if session_id else self.events
        
        flow = []
        for event in events:
            content = event.get_content()
            if content:
                flow.append((event.event_type.value, content))
        
        return flow
    
    def extract_multi_agent_interactions(self, session_id: Optional[str] = None) -> Dict[str, List[str]]:
        """Extract interactions between different agents.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            Dictionary mapping agent names to their contributions
        """
        events = self.get_events_by_session(session_id) if session_id else self.events
        
        agent_interactions = {}
        
        for event in events:
            agent_name = event.get_agent_name() or "unknown_agent"
            content = event.get_content()
            
            if content:
                if agent_name not in agent_interactions:
                    agent_interactions[agent_name] = []
                agent_interactions[agent_name].append(f"[{event.event_type.value}] {content}")
        
        return agent_interactions
    
    def get_streaming_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate a summary of the streaming session.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            Dictionary containing streaming session summary
        """
        events = self.get_events_by_session(session_id) if session_id else self.events
        
        if not events:
            return {"error": "No events to summarize"}
        
        # Count events by type
        event_counts = {}
        for event_type in StreamEventType:
            event_counts[event_type.value] = len([e for e in events if e.event_type == event_type])
        
        # Get unique agents
        agents = set()
        for event in events:
            agent_name = event.get_agent_name()
            if agent_name:
                agents.add(agent_name)
        
        # Calculate timing
        timestamps = [e.timestamp for e in events if e.timestamp]
        duration_seconds = None
        if len(timestamps) >= 2:
            duration = max(timestamps) - min(timestamps)
            duration_seconds = duration.total_seconds()
        
        # Extract errors
        errors = [event.get_content() for event in events if event.is_error_event()]
        
        return {
            "total_events": len(events),
            "event_counts": event_counts,
            "unique_agents": list(agents),
            "duration_seconds": duration_seconds,
            "has_errors": len(errors) > 0,
            "errors": errors,
            "session_id": session_id,
            "start_time": min(timestamps).isoformat() if timestamps else None,
            "end_time": max(timestamps).isoformat() if timestamps else None
        }
    
    def print_streaming_summary(self, session_id: Optional[str] = None):
        """Print a formatted summary of the streaming session."""
        summary = self.get_streaming_summary(session_id)
        
        print("\n" + "="*60)
        print("AGENTCORE STREAMING SESSION SUMMARY")
        print("="*60)
        
        if "error" in summary:
            print(f"Error: {summary['error']}")
            return
        
        print(f"Session ID: {summary['session_id'] or 'N/A'}")
        print(f"Total Events: {summary['total_events']}")
        print(f"Duration: {summary['duration_seconds']:.2f}s" if summary['duration_seconds'] else "Duration: N/A")
        print(f"Unique Agents: {', '.join(summary['unique_agents']) if summary['unique_agents'] else 'None'}")
        
        print(f"\nEvent Breakdown:")
        for event_type, count in summary['event_counts'].items():
            if count > 0:
                print(f"  {event_type}: {count}")
        
        if summary['has_errors']:
            print(f"\nErrors ({len(summary['errors'])}):")
            for i, error in enumerate(summary['errors'], 1):
                print(f"  {i}. {error}")
        
        print("="*60)
    
    def clear(self):
        """Clear all stored events and session data."""
        self.events.clear()
        self.session_events.clear()

def parse_streaming_response(streaming_data: Dict[str, Any]) -> StreamParser:
    """Convenience function to parse a streaming response.
    
    Args:
        streaming_data: Streaming response data containing events
        
    Returns:
        Configured StreamParser with parsed events
    """
    parser = StreamParser()
    
    if isinstance(streaming_data, dict) and "events" in streaming_data:
        events = streaming_data["events"]
        parser.parse_events(events)
    elif isinstance(streaming_data, list):
        parser.parse_events(streaming_data)
    else:
        logger.warning(f"Unexpected streaming data format: {type(streaming_data)}")
    
    return parser
