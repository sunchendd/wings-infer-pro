# G.OTH.01 安全场景下必须使用密码学意义上的安全随机数

- **规则ID**：87ebb1ab-db46-4e85-bd8b-e79e461d9448
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

一般

**【描述】**

不安全的随机数可能被部分或全部预测到，导致系统存在安全隐患，安全场景下使用的随机数必须是密码学意义上的安全随机数。密码学意义上的安全随机数分为两类：



- 真随机数产生器产生的随机数；

- 以真随机数产生器产生的少量随机数作为种子的密码学安全的伪随机数产生器产生的大量随机数。

已知的可供产品使用的密码学安全的非物理真随机数产生器有：Linux操作系统的/dev/random设备接口（存在阻塞问题）和Windows操作系统的CryptGenRandom()接口。



Java中的SecureRandom是一种密码学安全的伪随机数产生器，对于使用非真随机数产生器产生随机数时，要使用少量真随机数作为种子。



常见安全场景包括但不限于以下场景：



- 用于密码算法用途，如生成IV、盐值、密钥等；

- 会话标识（sessionId）的生成；

- 挑战算法中的随机数生成；

- 验证码的随机数生成；

**【正确示例】**

```
【正例】（存在较高的阻塞风险）
```java
public byte[] generateSalt() {
    byte[] salt = new byte[8];
    try {
        SecureRandom random = SecureRandom.getInstanceStrong();
        random.nextBytes(salt);
    } catch (NoSuchAlgorithmException ex) {
        // 处理异常
    }
    return salt;
}
```
Java 8中添加了SecureRandom.getInstanceStrong()方法，用于生成不同平台上的最强的SecureRandom实现的实例：windows下默认为Windows-PRNG (sun.security.mscapi.PRNG)，使用CryptGenRandom()方法产生随机数；Solaris/Linux/macOS平台下默认为NativePRNGBlocking (sun.security.provider.NativePRNG$Blocking)，在初始种子、获取随机数、生成种子等场景下都是来自于/dev/random中的随机数，所以存在阻塞问题。对于具体算法可通过java.security配置文件中的securerandom.strongAlgorithms配置项进行设置。该方式生成的随机数可以用于安全场景，linux场景下需要考虑阻塞问题，防止影响系统的可用性，阻塞问题可参考《密码算法应用规范》。
Android系统中，该方式默认采用的是SHA1PRNG，不符合安全要求。
【正例】（JDK 9+）
```java
public byte[] generateSalt() {
    byte[] salt = new byte[8];
    try {
        SecureRandom random = SecureRandom.getInstance("DRBG", DrbgParameters.instantiation(256, RESEED_ONLY, null));
        random.nextBytes(salt);
    } catch (NoSuchAlgorithmException ex) {
        // 处理异常
    }
    return salt;
}
```
从JDK 9开始，新增了由Sun提供的符合NIST SP 800 90-A标准的DRBG伪随机数产生器，包括HASH-DRBG、HMAC-DRBG、CTR-DRBG三种，且适用于各种OS，符合公司密码算法相关要求，在使用JDK 9及以上版本时，推荐优先使用该方式生成安全随机数。

```
**【错误示例】**

```
【反例】
```java
public byte[] generateSalt() {
    byte[] salt = new byte[8];
    Random random = new Random(123456L);
    random.nextBytes(salt);
    return salt;
}
```
Random生成是不安全随机数，不能用做盐值。
【反例】

```java
public byte[] generateSalt() {
    byte[] salt = new byte[8];
    SecureRandom random = new SecureRandom();
    random.nextBytes(salt);
    return salt;
}
```
new SecureRandom()在不同的操作系统下，使用不同的随机数生成器（windows下默认是SHA1PRNG(sun.security.provider.SecureRandom)、linux下默认是NativePRNG(sun.security.provider.NativePRNG)）。比如linux系统下，默认使用的随机数产生器使用的种子及生成的随机数都来源于/dev/urandom，生成的随机数是不安全随机数，不能用作盐值。
【反例】
```java
public byte[] generateSalt() {
    byte[] salt = new byte[8];
    try {
        SecureRandom random = SecureRandom.getInstance("SHA1PRNG", "SUN");
        random.setSeed(random.generateSeed(SEED_LEN)); // 频繁设置种子可能会导致阻塞
        random.nextBytes(salt);
    } catch (NoSuchAlgorithmException ex) {
        // 处理异常
    }
    return salt;
}
```
上述代码中，明确指定采用sun.security.provider.SecureRandom作为随机数产生器，然后使用generateSeed()方法产生的随机数作为种子，该方法产生的随机数默认为真随机数（如linux下从/dev/random获取）。上述代码实际是使用少量真随机数作为种子（种子长度推荐不少于64bytes），然后采用伪随机数产生器来产生随机数，为了避免linux下阻塞问题，要尽量重复使用随机数生成器，避免频繁设置种子。对于需要生成大量随机数的场景，需要周期性补充种子，SHA1PRNG算法目前业界没有明确标准，推荐获取2^32次随机数后设置一次种子（调用一次nextBytes()、nextInt()等都计为一次获取随机数操作）。

但是根据公司密码算法相关要求，从2023年开始将禁止使用SHA1PRNG算法生成安全随机数。

```
**【修复建议】**

参考华为Java语言编程规范 V5.x：https://openx.huawei.com/communityWikiDetails/?communityId=41&ibid=SPE1000000181&navid=NVI1000013186&token=eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJnMzAwNDI4MzAiLCJjcmVhdGVkIjoxNjgxODczODA0MTAwLCJJUCI6IjEwLjE3My45OS4xODciLCJleHAiOjE2ODQ0NjU4MDR9.HutZV2G3zpdbq8KVGsdni3Ujd6KWkAYCVj_P97NTmKt-zRDJ1odSQcC1u_6KIpYc9GmM1CiHz07FIJm67L0Q_Q
