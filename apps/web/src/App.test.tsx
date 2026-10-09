import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App, Orb } from './App';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe('connection boundaries',()=>{
  it('starts disconnected without fabricating model or task state',()=>{
    render(<App/>);expect(screen.getByText('Your personal intelligence.')).toBeInTheDocument();
    expect(screen.queryByText('Task monitor')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Local session token')).toHaveAttribute('type','password');
  });
  it('rejects a remote HTTP address in local mode before fetching',async()=>{
    const fetch=vi.fn();vi.stubGlobal('fetch',fetch);render(<App/>);
    fireEvent.change(screen.getByLabelText('Agent address'),{target:{value:'http://attacker.example'}});
    fireEvent.change(screen.getByLabelText('Local session token'),{target:{value:'private-session'}});
    fireEvent.click(screen.getByRole('button',{name:'Connect'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('loopback');expect(fetch).not.toHaveBeenCalled();
  });
  it('exposes actual orb state accessibly',()=>{
    render(<Orb state="thinking"/>);expect(screen.getByLabelText('ULTRON thinking')).toHaveClass('thinking');
  });
});
