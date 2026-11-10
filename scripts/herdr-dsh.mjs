#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { EventEmitter } from 'node:events';
import { readFileSync, realpathSync } from 'node:fs';
import { isAbsolute } from 'node:path';
import net from 'node:net';
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';

export class RpcPeer extends EventEmitter {
  constructor(child) {
    super();
    this.child = child;
    this.counter = 0;
    this.pending = new Map();
    this.buffer = '';
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', data => {
      this.buffer += data;
      if (this.buffer.length > 8 * 1024 * 1024) return this.fail(new Error('DSH protocol frame is too large'));
      let newline;
      while ((newline = this.buffer.indexOf('\n')) !== -1) {
        const line = this.buffer.slice(0, newline).trim();
        this.buffer = this.buffer.slice(newline + 1);
        if (!line) continue;
        let frame;
        try { frame = JSON.parse(line); }
        catch { this.fail(new Error('DSH emitted a non-protocol stdout line')); continue; }
        if (!frame || typeof frame !== 'object') { this.fail(new Error('Invalid DSH protocol frame')); continue; }
        if (Object.hasOwn(frame, 'id')) {
          const request = this.pending.get(frame.id);
          if (!request) continue;
          this.pending.delete(frame.id);
          clearTimeout(request.timer);
          if (frame.error) request.reject(new Error(frame.error.message || 'DSH request failed'));
          else request.resolve(frame.result);
        } else if (frame.method) {
          this.emit('notification', frame.method, frame.params);
        }
      }
    });
    child.on('error', error => this.fail(error));
    child.on('exit', (code, signal) => {
      this.exited = true;
      this.fail(new Error(`DSH exited (${signal || code})`));
      this.emit('exit', code, signal);
    });
  }

  fail(error) {
    this.failure ||= error;
    for (const request of this.pending.values()) {
      clearTimeout(request.timer);
      request.reject(error);
    }
    this.pending.clear();
    this.emit('fault', error);
  }

  request(method, params, timeout = 30000) {
    if (this.exited) return Promise.reject(new Error('DSH is not running'));
    if (this.failure) return Promise.reject(this.failure);
    const id = ++this.counter;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`DSH ${method} timed out`));
      }, timeout);
      this.pending.set(id, { resolve, reject, timer });
      this.child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, ...(params === undefined ? {} : { params }) }) + '\n', error => {
        if (!error) return;
        const request = this.pending.get(id);
        if (!request) return;
        this.pending.delete(id);
        clearTimeout(timer);
        reject(error);
      });
    });
  }
}

export class AgentStateBridge {
  constructor(sessionId, publish) {
    this.sessionId = sessionId;
    this.publish = publish;
    this.ready = false;
    this.failed = false;
    this.state = undefined;
    this.observed = undefined;
    this.released = false;
  }

  becomeReady() {
    this.ready = true;
    this.setState(this.observed || 'idle');
  }

  setState(state, message) {
    if (!this.ready || this.released) return;
    if (state === this.state && !message) return;
    this.state = state;
    this.publish('state', state, message);
  }

  observe(method, params) {
    if (this.released || params?.sessionId !== this.sessionId) return;
    if (method === 'session.status') {
      if (params.status === 'running') {
        this.failed = false;
        this.observed = 'working';
        this.setState('working');
      } else if (params.status === 'idle' && !this.failed) {
        this.observed = 'idle';
        this.setState('idle');
      }
    }
    if (method === 'session.event' && params.event?.type === 'turn/end') {
      const reason = params.event.data?.reason;
      if (reason?.kind === 'error' || reason?.kind === 'blocked') {
        this.failed = true;
        this.observed = 'blocked';
        this.setState('blocked', reason.error?.message || 'DSH needs input');
      }
    }
  }

  release() {
    if (this.released) return;
    this.released = true;
    if (this.ready) this.publish('release');
  }
}

export function createReporter(env, sessionId, provider, model, resumeArgv) {
  const source = 'dsh-sdk-herdr';
  let sequence = Date.now() * 1000;
  let tail = Promise.resolve();
  const send = request => new Promise(resolve => {
    if (env.HERDR_ENV !== '1' || !env.HERDR_SOCKET_PATH || !env.HERDR_PANE_ID) return resolve();
    const socket = net.createConnection(env.HERDR_SOCKET_PATH);
    const finish = () => { socket.destroy(); resolve(); };
    socket.setTimeout(1000, finish);
    socket.on('error', finish);
    socket.on('end', finish);
    socket.on('data', finish);
    socket.on('connect', () => socket.write(JSON.stringify(request) + '\n'));
  });
  const publish = (kind, state, message) => {
    const seq = ++sequence;
    const params = { pane_id: env.HERDR_PANE_ID, source, agent: 'dsh', seq };
    const request = {
      id: `${source}:${seq}`,
      method: kind === 'release' ? 'pane.release_agent' : 'pane.report_agent',
      params: kind === 'release' ? params : {
        ...params, state, ...(message ? { message } : {}),
        agent_session_id: sessionId,
        resume_argv: [...resumeArgv, '--session', sessionId, '--provider', provider, '--model', model],
      },
    };
    tail = tail.then(() => send(request));
  };
  return { publish, flush: () => tail };
}

function fields(value, required, optional = []) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || required.some(key => !Object.hasOwn(value, key))
      || Object.keys(value).some(key => ![...required, ...optional].includes(key))) {
    throw new Error('Invalid layout fields');
  }
}

function singleLine(value) {
  return typeof value === 'string' && value.length > 0 && !/['\x00-\x1f]/.test(value);
}

function absolutePath(value) {
  return typeof value === 'string' && value.length > 0 && !/[\x00-\x1f]/.test(value) && isAbsolute(value);
}

export function loadLayout(path) {
  if (!absolutePath(path)) throw new Error('--layout requires an absolute private JSON path');
  const layout = JSON.parse(readFileSync(path, 'utf8'));
  fields(layout, ['dsh_bin', 'profile', 'provider', 'model', 'reporter', 'resume_argv'], ['dsh_home']);
  if (!absolutePath(layout.dsh_bin)) throw new Error('dsh_bin must be an absolute path');
  if (Object.hasOwn(layout, 'dsh_home') && !absolutePath(layout.dsh_home)) throw new Error('dsh_home must be an absolute path');
  if (![layout.profile, layout.provider, layout.model].every(singleLine)) throw new Error('Profile, provider and model must be single-line values without apostrophes');
  if (!Array.isArray(layout.resume_argv) || !layout.resume_argv.length
      || !absolutePath(layout.resume_argv[0])
      || layout.resume_argv.some(value => typeof value !== 'string' || value.includes('\0'))) {
    throw new Error('resume_argv requires an absolute executable and literal string arguments');
  }
  fields(layout.reporter, ['mode'], ['env']);
  if (layout.reporter.mode === 'disabled') {
    if (Object.hasOwn(layout.reporter, 'env')) throw new Error('Disabled reporter has no env view');
  } else if (layout.reporter.mode === 'herdr') {
    fields(layout.reporter.env, ['HERDR_ENV', 'HERDR_SOCKET_PATH', 'HERDR_PANE_ID']);
    const env = layout.reporter.env;
    if (env.HERDR_ENV !== '1' || !absolutePath(env.HERDR_SOCKET_PATH) || !singleLine(env.HERDR_PANE_ID)) {
      throw new Error('Herdr reporter requires explicit enabled marker, socket path and pane ID');
    }
  } else {
    throw new Error('reporter mode must be disabled or herdr');
  }
  return layout;
}

export function parseArgs(args) {
  const overrides = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--help' || args[i] === '-h') return { help: true };
    if (!['--layout', '--provider', '--model', '--session'].includes(args[i]) || !args[i + 1]) throw new Error('Unknown or incomplete argument: ' + args[i]);
    overrides[args[i].slice(2)] = args[++i];
  }
  const layout = loadLayout(overrides.layout);
  const options = { layout, provider: overrides.provider ?? layout.provider,
                    model: overrides.model ?? layout.model,
                    ...(overrides.session ? { session: overrides.session } : {}) };
  if (![options.provider, options.model, ...(options.session ? [options.session] : [])].every(singleLine)) throw new Error('Arguments must be single-line values without apostrophes');
  return options;
}

export async function main(args = process.argv.slice(2)) {
  const options = parseArgs(args);
  if (options.help) {
    console.log('herdr-dsh.mjs --layout /absolute/private.json [--provider NAME] [--model ID] [--session UUID]\n\nDSH terminal client. Commands: /status, /quit. Ctrl+C exits.');
    return;
  }
  const sessionId = options.session || randomUUID();
  const layout = options.layout;
  const reporterEnv = layout.reporter.mode === 'herdr' ? layout.reporter.env : {};
  const reporter = createReporter(reporterEnv, sessionId, options.provider, options.model, layout.resume_argv);
  const state = new AgentStateBridge(sessionId, reporter.publish);
  const child = spawn(layout.dsh_bin, ['--profile', layout.profile], {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: layout.dsh_home ? { ...process.env, DSH_HOME: layout.dsh_home } : process.env,
  });
  const peer = new RpcPeer(child);
  let terminal;
  let stopping;
  let fault;
  const diagnostics = [];
  child.stderr.setEncoding('utf8');
  child.stderr.on('data', data => {
    diagnostics.push(data);
    if (diagnostics.join('').length > 8192) diagnostics.shift();
  });
  peer.on('fault', error => { fault = error; });
  peer.on('notification', (method, params) => {
    state.observe(method, params);
    if (params?.sessionId !== sessionId || method !== 'session.event') return;
    const event = params.event;
    if (event?.type === 'assistant/message') {
      const content = Array.isArray(event.data?.message?.content) ? event.data.message.content : [];
      const text = content.filter(block => block.type === 'text').map(block => block.text || '').join('');
      if (text) console.log('\n' + text);
    }
    if (event?.type === 'tool/call') console.log(`\n[${event.data?.name || 'tool'}]`);
    if (event?.type === 'turn/end' && event.data?.reason?.kind === 'error') console.error('\n' + (event.data.reason.error?.message || 'DSH turn failed'));
  });
  const stop = () => {
    if (stopping) return stopping;
    stopping = (async () => {
      terminal?.close();
      if (!peer.exited) {
        try { await peer.request('shutdown', undefined, 5000); }
        catch { child.kill('SIGTERM'); }
        child.stdin.end();
        const exited = await new Promise(resolve => {
          if (peer.exited) return resolve(true);
          const timer = setTimeout(() => { child.off('exit', done); resolve(false); }, 5000);
          const done = () => { clearTimeout(timer); resolve(true); };
          child.once('exit', done);
        });
        if (!exited && !peer.exited) child.kill('SIGTERM');
      }
      state.release();
      await reporter.flush();
    })();
    return stopping;
  };
  const onSignal = () => { void stop(); };
  process.on('SIGINT', onSignal);
  process.on('SIGTERM', onSignal);
  peer.on('exit', () => { if (state.ready && !stopping) void stop(); });
  peer.on('fault', error => {
    if (state.ready && !stopping) { console.error(error.message); void stop(); }
  });
  try {
    console.log('DSH starting…');
    const initialized = await peer.request('initialize', {
      cwd: process.cwd(), provider: options.provider, model: options.model,
    });
    if (initialized?.serverInfo?.name !== 'deepseek-harness-sdk-runtime') throw new Error('Unexpected DSH runtime identity');
    if (options.session) await peer.request('session/resume', { sessionId });
    else await peer.request('session/working-directory/get', { sessionId });
    state.becomeReady();
    await reporter.flush();
    console.log(`DSH · ${options.model}\nSession: ${sessionId}\n/status  /quit`);
    terminal = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: process.stdin.isTTY });
    terminal.setPrompt('dsh> ');
    terminal.prompt();
    terminal.on('SIGINT', onSignal);
    for await (const line of terminal) {
      const text = line.trim();
      if (text === '/quit' || text === '/exit') break;
      if (text === '/status') {
        console.log(`${state.state} · ${options.provider}/${options.model} · ${sessionId}`);
      } else if (text) {
        try {
          await peer.request('session/prompt', { sessionId, contentBlocks: [{ type: 'text', text }] });
          // Admission is not a lifecycle transition. Only the SDK's actual
          // session.status and turn/end notifications update Herdr.
          await peer.request('session/wait', { sessionId }, 24 * 60 * 60 * 1000);
        } catch (error) {
          console.error(error.message);
        }
      }
      terminal.prompt();
    }
  } catch (error) {
    console.error(`DSH startup failed: ${error.message}`);
    if (fault && fault.message !== error.message) console.error(fault.message);
    const diagnostic = diagnostics.join('').trim();
    if (diagnostic) console.error(diagnostic);
    process.exitCode = 1;
  } finally {
    await stop();
    process.off('SIGINT', onSignal);
    process.off('SIGTERM', onSignal);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
