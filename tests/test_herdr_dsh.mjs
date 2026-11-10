import assert from 'node:assert/strict';
import childProcess from 'node:child_process';
import { EventEmitter, once } from 'node:events';
import { chmodSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { syncBuiltinESMExports } from 'node:module';
import net from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import readline from 'node:readline';
import { PassThrough, Writable } from 'node:stream';
import { setImmediate as tick } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import { AgentStateBridge, RpcPeer, createReporter, loadLayout, main, parseArgs } from '../scripts/herdr-dsh.mjs';

const ADAPTER = fileURLToPath(new URL('../scripts/herdr-dsh.mjs', import.meta.url));

function temporary(t) {
  const root = mkdtempSync(join(tmpdir(), 'dsh fixture '));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return root;
}

function layoutFixture(t) {
  const root = temporary(t);
  const path = join(root, 'private layout.json');
  const value = { dsh_bin: join(root, 'fake dsh'), profile: 'fixture-sdk',
    provider: 'fixture-provider', model: 'fixture-model', reporter: { mode: 'disabled' },
    resume_argv: [process.execPath, ADAPTER, '--layout', path] };
  const save = () => writeFileSync(path, JSON.stringify(value));
  save();
  return { root, path, value, save };
}

function syntheticChild(onRequest) {
  const child = new EventEmitter();
  child.stdout = new PassThrough();
  child.stderr = new PassThrough();
  child.requests = [];
  child.kills = [];
  child.stdin = new Writable({ write(data, encoding, callback) {
    const frame = JSON.parse(data.toString());
    child.requests.push(frame);
    if (onRequest) onRequest(frame, child);
    callback();
  } });
  child.reply = (frame, result = {}) => child.stdout.write(JSON.stringify({ id: frame.id, result }) + '\n');
  child.notify = (method, params) => child.stdout.write(JSON.stringify({ method, params }) + '\n');
  child.kill = signal => { child.kills.push(signal); child.emit('exit', null, signal); return true; };
  return child;
}

test('RPC handles split/multiple frames, increasing IDs, notifications and remote errors', async () => {
  const child = syntheticChild();
  const peer = new RpcPeer(child);
  const notifications = [];
  peer.on('notification', (...args) => notifications.push(args));
  const first = peer.request('first');
  const second = peer.request('second', { value: 2 });
  const failed = assert.rejects(second, /remote failure/);
  assert.deepEqual(child.requests.map(frame => frame.id), [1, 2]);
  assert.equal(Object.hasOwn(child.requests[0], 'params'), false);
  child.stdout.write('{"id":1,"res');
  child.stdout.write('ult":{"ok":true}}\n\n{"method":"notice","params":3}\n');
  child.stdout.write('{"id":999,"result":null}\n{"id":2,"error":{"message":"remote failure"}}\n');
  assert.deepEqual(await first, { ok: true });
  await failed;
  assert.deepEqual(notifications, [['notice', 3]]);
  assert.equal(peer.pending.size, 0);
});

test('RPC malformed frames and JS-length buffer overflow fail pending requests', async () => {
  for (const [payload, message] of [['not json\n', /non-protocol/], ['null\n', /Invalid/],
    ['界'.repeat(8 * 1024 * 1024 + 1), /too large/]]) {
    const child = syntheticChild();
    const peer = new RpcPeer(child);
    const rejected = assert.rejects(peer.request('pending'), message);
    child.stdout.write(payload);
    await rejected;
    await assert.rejects(peer.request('after failure'), message);
    assert.equal(peer.pending.size, 0);
  }
  const child = syntheticChild();
  const peer = new RpcPeer(child);
  const pending = peer.request('unicode');
  const belowLength = '界'.repeat(3 * 1024 * 1024);
  assert.ok(Buffer.byteLength(belowLength, 'utf8') > 8 * 1024 * 1024);
  child.stdout.write(belowLength);
  assert.equal(peer.failure, undefined);
  const rejected = assert.rejects(pending, /fixture ended/);
  peer.fail(new Error('fixture ended'));
  await rejected;
});

test('RPC timeout, write callback error, child error and exit propagate', async () => {
  const timeoutChild = syntheticChild();
  const timeoutPeer = new RpcPeer(timeoutChild);
  await assert.rejects(timeoutPeer.request('slow', undefined, 5), /slow timed out/);
  assert.equal(timeoutPeer.pending.size, 0);
  const writeChild = syntheticChild();
  writeChild.stdin = { write(data, callback) { callback(new Error('write failed')); } };
  await assert.rejects(new RpcPeer(writeChild).request('write'), /write failed/);
  for (const event of ['error', 'exit']) {
    const child = syntheticChild();
    const peer = new RpcPeer(child);
    const rejected = assert.rejects(peer.request('pending'), event === 'error' ? /child failure/ : /DSH exited/);
    if (event === 'error') child.emit('error', new Error('child failure'));
    else child.emit('exit', 12, null);
    await rejected;
    assert.equal(peer.pending.size, 0);
    if (event === 'exit') await assert.rejects(peer.request('again'), /not running/);
  }
});

test('state bridge filters sessions, waits for ready and retains blocked until running', () => {
  const published = [];
  const state = new AgentStateBridge('fixture-session', (...args) => published.push(args));
  state.observe('session.status', { sessionId: 'other', status: 'running' });
  assert.equal(state.observed, undefined);
  state.observe('session.status', { sessionId: 'fixture-session', status: 'running' });
  assert.equal(published.length, 0);
  state.becomeReady();
  state.observe('session.event', { sessionId: 'fixture-session', event: {
    type: 'turn/end', data: { reason: { kind: 'blocked' } } } });
  state.observe('session.status', { sessionId: 'fixture-session', status: 'idle' });
  assert.equal(state.state, 'blocked');
  state.observe('session.status', { sessionId: 'fixture-session', status: 'running' });
  state.observe('session.status', { sessionId: 'fixture-session', status: 'idle' });
  state.observe('session.status', { sessionId: 'fixture-session', status: 'idle' });
  state.release();
  state.release();
  state.observe('session.status', { sessionId: 'fixture-session', status: 'running' });
  assert.deepEqual(published.map(value => value.slice(0, 2)),
    [['state', 'working'], ['state', 'blocked'], ['state', 'working'], ['state', 'idle'], ['release']]);
  const beforeReady = [];
  new AgentStateBridge('fixture-session', (...args) => beforeReady.push(args)).release();
  assert.deepEqual(beforeReady, []);
});

test('disabled reporter never connects despite inherited Herdr environment', async t => {
  t.mock.method(net, 'createConnection', () => { throw new Error('No socket allowed'); });
  const reporter = createReporter({}, 'fixture-session', 'p', 'm', ['/example/node']);
  reporter.publish('state', 'working');
  reporter.publish('release');
  await reporter.flush();
  assert.equal(net.createConnection.mock.callCount(), 0);
});

test('reporter serializes literal resume argv and preserves weak data/end/error/timeout completion', async t => {
  const sockets = [];
  const sent = [];
  t.mock.method(net, 'createConnection', path => {
    assert.equal(path, '/example/private/herdr.sock');
    const socket = new EventEmitter();
    socket.setTimeout = (milliseconds, callback) => { assert.equal(milliseconds, 1000); socket.timeout = callback; };
    socket.destroy = () => { socket.destroyed = true; };
    socket.write = data => sent.push(JSON.parse(data));
    sockets.push(socket);
    queueMicrotask(() => socket.emit('connect'));
    return socket;
  });
  const prefix = ['/example/node', '/example/adapter.mjs', '--layout', '/example/private/layout.json', 'literal space'];
  const reporter = createReporter({ HERDR_ENV: '1', HERDR_SOCKET_PATH: '/example/private/herdr.sock',
    HERDR_PANE_ID: 'fixture-pane' }, 'fixture-session', 'p', 'm', prefix);
  for (let i = 0; i < 3; i++) reporter.publish('state', 'working');
  reporter.publish('release');
  await tick();
  assert.equal(sockets.length, 1);
  for (const [index, outcome] of ['data', 'end', 'error', 'timeout'].entries()) {
    const socket = sockets[index];
    assert.ok(socket);
    if (outcome === 'timeout') socket.timeout();
    else socket.emit(outcome, outcome === 'error' ? new Error('synthetic refusal') : Buffer.from('not an ACK'));
    await tick();
    assert.equal(socket.destroyed, true);
    assert.equal(sockets.length, Math.min(index + 2, 4));
  }
  await reporter.flush();
  assert.deepEqual(sent[0].params.resume_argv,
    [...prefix, '--session', 'fixture-session', '--provider', 'p', '--model', 'm']);
  assert.equal(sent[0].params.pane_id, 'fixture-pane');
  assert.equal(sent[3].method, 'pane.release_agent');
  assert.equal(Object.hasOwn(sent[3].params, 'resume_argv'), false);
  assert.deepEqual(sent.map(item => item.params.seq - sent[0].params.seq), [0, 1, 2, 3]);
});

test('explicit layout and CLI override precedence reject missing or invalid inputs', t => {
  const fixture = layoutFixture(t);
  assert.deepEqual(loadLayout(fixture.path), fixture.value);
  assert.equal(parseArgs(['--layout', fixture.path]).provider, 'fixture-provider');
  const selected = parseArgs(['--provider', 'override-p', '--layout', fixture.path,
    '--session', 'literal-session', '--model', 'override-m']);
  assert.deepEqual([selected.provider, selected.model, selected.session], ['override-p', 'override-m', 'literal-session']);
  assert.deepEqual(parseArgs(['--help']), { help: true });
  for (const args of [[], ['--layout'], ['--layout', 'relative'], ['--unknown', 'x'],
    ['--layout', fixture.path, '--provider', "bad'value"], ['--layout', fixture.path, '--model', 'bad\nvalue']]) {
    assert.throws(() => parseArgs(args));
  }
  for (const replacement of [{}, { dsh_bin: 'relative' }, { profile: '' }, { model: 'bad\tvalue' },
    { reporter: { mode: 'inherit' } }, { reporter: { mode: 'disabled', env: {} } },
    { reporter: { mode: 'herdr', env: { HERDR_ENV: '1' } } }, { resume_argv: [] },
    { resume_argv: ['/example/node', '\0'] }, { dsh_home: 'relative' }, { unknown: true }]) {
    writeFileSync(fixture.path, JSON.stringify(Object.keys(replacement).length ? { ...fixture.value, ...replacement } : {}));
    assert.throws(() => loadLayout(fixture.path));
  }
  fixture.value.reporter = { mode: 'herdr', env: { HERDR_ENV: '1',
    HERDR_SOCKET_PATH: join(fixture.root, 'unused.sock'), HERDR_PANE_ID: 'explicit-pane' } };
  fixture.save();
  assert.deepEqual(loadLayout(fixture.path).reporter, fixture.value.reporter);
});

async function runMockMain(t, { session, serverName = 'deepseek-harness-sdk-runtime', shutdownError = false,
  signals = false, dshHome = true, prompt = true } = {}) {
  const fixture = layoutFixture(t);
  if (dshHome) fixture.value.dsh_home = join(fixture.root, 'child home');
  fixture.save();
  const stdout = [];
  const stderr = [];
  const states = [];
  const inheritedHome = process.env.DSH_HOME;
  const oldExitCode = process.exitCode;
  const listeners = ['SIGINT', 'SIGTERM'].map(name => process.listenerCount(name));
  const child = syntheticChild((frame, own) => queueMicrotask(() => {
    if (frame.method === 'initialize') own.reply(frame, { serverInfo: { name: serverName, version: 'different-wire-version' } });
    else if (frame.method === 'shutdown') {
      if (shutdownError) own.stdout.write(JSON.stringify({ id: frame.id, error: { message: 'shutdown refused' } }) + '\n');
      else { own.reply(frame); queueMicrotask(() => own.emit('exit', 0, null)); }
    } else {
      if (frame.method === 'session/prompt') {
        own.notify('session.event', { sessionId: 'wrong-session', event: { type: 'assistant/message',
          data: { message: { content: [{ type: 'text', text: 'SHOULD_NOT_APPEAR' }] } } } });
        own.notify('session.status', { sessionId: frame.params.sessionId, status: 'running' });
        own.notify('session.event', { sessionId: frame.params.sessionId, event: { type: 'assistant/message',
          data: { message: { content: [{ type: 'text', text: 'fixture answer' }] } } } });
        own.notify('session.event', { sessionId: frame.params.sessionId, event: { type: 'tool/call', data: { name: 'fixture-tool' } } });
      }
      if (frame.method === 'session/wait') own.notify('session.status', { sessionId: frame.params.sessionId, status: 'idle' });
      own.reply(frame);
    }
  }));
  const spawnCalls = [];
  t.mock.method(childProcess, 'spawn', (...args) => { spawnCalls.push(args); return child; });
  syncBuiltinESMExports();
  t.mock.method(net, 'createConnection', () => { throw new Error('No socket allowed'); });
  t.mock.method(console, 'log', value => stdout.push(value));
  t.mock.method(console, 'error', value => stderr.push(value));
  const observeOriginal = AgentStateBridge.prototype.setState;
  t.mock.method(AgentStateBridge.prototype, 'setState', function (...args) {
    states.push(args[0]); return observeOriginal.apply(this, args);
  });
  const terminal = new EventEmitter();
  terminal.closed = 0;
  terminal.close = () => { terminal.closed++; };
  terminal.setPrompt = () => {};
  terminal.prompt = () => {
    if (signals) { process.emit('SIGINT'); process.emit('SIGTERM'); }
  };
  terminal[Symbol.asyncIterator] = async function* () {
    for (const line of prompt ? ['fixture question', '/status', '/quit'] : ['/quit']) {
      if (terminal.closed) return;
      yield line;
    }
  };
  t.mock.method(readline, 'createInterface', () => terminal);
  try {
    await main(['--layout', fixture.path, ...(session ? ['--session', session] : [])]);
    assert.equal(process.env.DSH_HOME, inheritedHome);
    assert.deepEqual(['SIGINT', 'SIGTERM'].map(name => process.listenerCount(name)), listeners);
    return { fixture, child, stdout, stderr, states, spawnCalls, terminal, exitCode: process.exitCode };
  } finally {
    process.exitCode = oldExitCode;
    t.mock.restoreAll();
    syncBuiltinESMExports();
  }
}

test('main keeps name-only handshake, new UUID, cwd, prompt/wait and own-child clean shutdown', async t => {
  const result = await runMockMain(t);
  const { child, spawnCalls, fixture } = result;
  assert.deepEqual(spawnCalls[0].slice(0, 2), [fixture.value.dsh_bin, ['--profile', 'fixture-sdk']]);
  assert.equal(spawnCalls[0][2].env.DSH_HOME, fixture.value.dsh_home);
  assert.deepEqual(child.requests.map(value => value.method),
    ['initialize', 'session/working-directory/get', 'session/prompt', 'session/wait', 'shutdown']);
  assert.deepEqual(child.requests[0].params, { cwd: process.cwd(), provider: 'fixture-provider', model: 'fixture-model' });
  const session = child.requests[1].params.sessionId;
  assert.match(session, /^[0-9a-f-]{36}$/);
  assert.equal(child.requests[2].params.sessionId, session);
  assert.ok(result.stdout.some(value => value.includes('fixture answer')));
  assert.ok(result.stdout.some(value => value.includes('[fixture-tool]')));
  assert.equal(result.stdout.some(value => value.includes('SHOULD_NOT_APPEAR')), false);
  assert.deepEqual(result.states, ['idle', 'working', 'idle']);
  assert.deepEqual(child.kills, []);
  assert.equal(result.terminal.closed, 1);
  assert.deepEqual(result.stderr, []);
});

test('explicit session resumes and absent dsh_home retains original child environment', async t => {
  const result = await runMockMain(t, { session: 'fixture-explicit-session', dshHome: false, prompt: false });
  assert.equal(result.child.requests[1].method, 'session/resume');
  assert.deepEqual(result.child.requests[1].params, { sessionId: 'fixture-explicit-session' });
  assert.equal(result.spawnCalls[0][2].env, process.env);
});

test('wrong runtime name fails before ready and still shuts down only its child', async t => {
  const result = await runMockMain(t, { serverName: 'unexpected-name' });
  assert.equal(result.exitCode, 1);
  assert.deepEqual(result.child.requests.map(frame => frame.method), ['initialize', 'shutdown']);
  assert.deepEqual(result.states, []);
  assert.ok(result.stderr.some(line => line.includes('Unexpected DSH runtime identity')));
  assert.deepEqual(result.child.kills, []);
});

test('duplicate stop signals share shutdown and failed shutdown SIGTERMs only owned child', async t => {
  const result = await runMockMain(t, { signals: true, shutdownError: true, prompt: false });
  assert.equal(result.child.requests.filter(frame => frame.method === 'shutdown').length, 1);
  assert.deepEqual(result.child.kills, ['SIGTERM']);
  assert.equal(result.terminal.closed, 1);
});

test('direct entry uses only temporary fake SDK, explicit argv/home and piped conversation', { timeout: 10000 }, async t => {
  const fixture = layoutFixture(t);
  const events = join(fixture.root, 'fake-sdk-events.jsonl');
  const sdk = join(fixture.root, 'fake SDK.mjs');
  writeFileSync(sdk, `import { appendFileSync } from 'node:fs';
import readline from 'node:readline';
const save = value => appendFileSync(process.env.DSH_FIXTURE_EVENTS, JSON.stringify(value) + '\\n');
save({kind:'spawn', argv:process.argv.slice(2), cwd:process.cwd(), home:process.env.DSH_HOME});
const lines = readline.createInterface({input:process.stdin});
for await (const line of lines) {
  const frame=JSON.parse(line); save(frame);
  const result=frame.method==='initialize' ? {serverInfo:{name:'deepseek-harness-sdk-runtime',version:'fixture-only'}} : {};
  process.stdout.write(JSON.stringify({id:frame.id,result})+'\\n');
  if(frame.method==='shutdown') break;
}
`);
  const quote = value => "'" + value.replaceAll("'", "'\\''") + "'";
  writeFileSync(fixture.value.dsh_bin, '#!/bin/sh\nexec ' + quote(process.execPath) + ' ' + quote(sdk) + ' "$@"\n');
  chmodSync(fixture.value.dsh_bin, 0o700);
  fixture.value.dsh_home = join(fixture.root, 'explicit fake home');
  fixture.save();
  const child = childProcess.spawn(process.execPath, [ADAPTER, '--layout', fixture.path, '--provider', 'override-provider'],
    { cwd: fixture.root, env: { ...process.env, DSH_FIXTURE_EVENTS: events }, stdio: ['pipe', 'pipe', 'pipe'] });
  t.after(() => { if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM'); });
  let stdout = '';
  let stderr = '';
  let sent = false;
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', data => {
    stdout += data;
    if (!sent && stdout.includes('dsh> ')) { sent = true; child.stdin.write('fixture prompt\n/quit\n'); }
  });
  child.stderr.on('data', data => { stderr += data; });
  const [code, signal] = await once(child, 'close');
  assert.deepEqual([code, signal, stderr], [0, null, '']);
  const recorded = readFileSync(events, 'utf8').trim().split('\n').map(line => JSON.parse(line));
  assert.deepEqual(recorded[0], { kind: 'spawn', argv: ['--profile', 'fixture-sdk'],
    cwd: realpathSync(fixture.root), home: fixture.value.dsh_home });
  assert.deepEqual(recorded.slice(1).map(frame => frame.method),
    ['initialize', 'session/working-directory/get', 'session/prompt', 'session/wait', 'shutdown']);
  assert.equal(recorded[1].params.provider, 'override-provider');
  assert.equal(recorded[1].params.cwd, realpathSync(fixture.root));
  assert.ok(stdout.includes('Session: '));
});
