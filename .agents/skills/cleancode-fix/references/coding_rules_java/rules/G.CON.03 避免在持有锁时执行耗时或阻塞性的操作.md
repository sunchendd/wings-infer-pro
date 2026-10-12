# G.CON.03 避免在持有锁时执行耗时或阻塞性的操作

- **规则ID**：516eff9d-e589-4ef3-affc-c4962800e327
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

一般

**【描述】**

持有锁时执行耗时或阻塞性操作会严重降低系统性能，且可能导致线程饥饿。此外可能会导致依赖本线程的其它线程无限期阻塞。阻塞性操作包括网络、文件、控制台I/O和对象序列化等，线程无限期的等待也属于阻塞性的操作。

**【正确示例】**

```
private List<Message> messageBuff = new ArrayList[MAX_BUFF_SIZE];

public void sendMessage(Socket socket, String targetUid) throws IOException {
    List<Message> candidateMessage = getCandidateMessage(targetUid);
    if (!candidateMessage.isEmpty()) {
        writeMessageToStream(socket, candidateMessage);
    }
}

public List<Message> getCandidateMessage(String targetUid) {
    List<Message> candidates = new ArrayList<>();
    synchronized (messageBuff) {
        Iterator<Message> iterator = messageBuff.iterator();
        while (iterator.hasNext()) {
            Message msg = iterator.next();
            if (msg.getTargetUid().equals(targetUid)) {
                candidates.add(msg);
                iterator.remove();
            }
        }
    }
    return candidates;
}

public void writeMessageToStream(Socket socket, List<Message> messages)
    throws IOException {
    try (ObjectOutputStream out = new ObjectOutputStream(socket.getOutputStream())) {
        for (Message message : messages) {
            out.writeObject(message);
        }
    }
}

上述示例中，把处理方法分成两个部分，在getCandidateMessage方法中完成对messageBuff的加锁访问，然后调用不需要同步的writeMessageToStream方法，完成IO操作。

```
**【错误示例】**

```
private List<Message> messageBuff = new ArrayList[MAX_BUFF_SIZE];

public void sendMessage(Socket socket, String targetUid) throws IOException {
    try (ObjectOutputStream out = new ObjectOutputStream(socket.getOutputStream())) {
        synchronized(messageBuff) {
            Iterator<Message> iterator = messageBuff.iterator();
            while (iterator.hasNext()) {
                Message message = iterator.next();
                if (message.getTargetUid().equals(targetUid)) {
                    out.writeObject(message);
                    iterator.remove();
                }
            }
        }
    }
}

上述示例中，定义了一个sendMessage的方法，加synchronized的目的是为了多线程并发场景下，保护messageBuff。但是writeObject方法是一个网络IO操作，属于阻塞性操作，在高时延、网络丢包的情况下会导致线程的长时间等待，就像死锁一样。

```
**【修复建议】**

对共享变量做同步访问控制时需避开同步陷阱
