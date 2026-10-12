# SecJ_Object_Signed_Encrypted

- **规则ID**：25fefd5e-5ff4-4b77-851e-9ca5d788a6df
- **更新时间**：2025-06-05 04:00:03

---

**【问题级别】**

一般

**【描述】**

敏感数据传输过程中要防止被窃取和恶意篡改。使用安全的加密算法加密传输对象可以保护数据。这就是所谓的对对象进行密封。而对密封的对象进行数字签名则可以防止对象被非法篡改，保持其完整性。

**【正确示例】**

```
public void testGood() throws IOException, ClassNotFoundException, GeneralSecurityException {
    // Build map
    SerializableMap<String, Integer> map = MapSerializer.buildMap();
    // Generate signing public/private key pair & sign map
    KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
    KeyPair kp = kpg.generateKeyPair();
    Signature sig = Signature.getInstance("SHA256withRSA");
    SignedObject signedMap = new SignedObject(map, kp.getPrivate(), sig);
    // Generate sealing key & seal map
    KeyGenerator generator = KeyGenerator.getInstance("AES");

    generator.init(new SecureRandom());
    Key key = generator.generateKey();
    Cipher cipher = Cipher.getInstance("AES");
    cipher.init(Cipher.ENCRYPT_MODE, key);
    SealedObject sealedMap = new SealedObject(signedMap, cipher);
    // Serialize map
    ObjectOutputStream out = new ObjectOutputStream(new FileOutputStream("data"));
    out.writeObject(sealedMap);
    out.close();
}

```
**【错误示例】**

```
public void test01Bad() throws IOException, ClassNotFoundException, GeneralSecurityException {
    // Build map
    SerializableMap<String, Integer> map = MapSerializer.buildMap();
    // Generate sealing key & seal map
    KeyGenerator generator = KeyGenerator.getInstance("AES");
    generator.init(new SecureRandom());
    Key key = generator.generateKey();
    Cipher cipher = Cipher.getInstance("AES");
    cipher.init(Cipher.ENCRYPT_MODE, key);
    SealedObject sealedMap = new SealedObject(map, cipher);
    // Generate signing public/private key pair & sign map
    KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
    KeyPair kp = kpg.generateKeyPair();
    Signature sig = Signature.getInstance("SHA256withRSA");
    SignedObject signedMap = new SignedObject(sealedMap, kp.getPrivate(), sig);
    // Serialize map
    ObjectOutputStream out = new ObjectOutputStream(new FileOutputStream("data"));
    /* POTENTIAL FLAW: 序列化时，先做加密，后做签名。 */
    out.writeObject(signedMap);
    out.close();
}

```
**【修复建议】**
