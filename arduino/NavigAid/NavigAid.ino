#include <Wire.h>
#include <VL53L0X.h>
#include "I2Cdev.h"
#include "MPU6050.h"

#define TRIG_LEFT 7
#define ECHO_LEFT 6
#define TRIG_RIGHT 3
#define ECHO_RIGHT 2

#define IN1 8
#define IN2 9
#define IN3 10
#define IN4 11

VL53L0X laser;
MPU6050 mpu;

float readUS(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  long duration = pulseIn(echo, HIGH);
  return duration * 0.034 / 2;
}

void moveForward() {
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
}

void moveLeft() {
  digitalWrite(IN1, LOW);  digitalWrite(IN2, HIGH);   // left motor: backward
  digitalWrite(IN3, LOW);  digitalWrite(IN4, HIGH);  // right motor: forward
}

void moveRight() {
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);   // left motor: forward
  digitalWrite(IN3, HIGH);  digitalWrite(IN4, LOW);   // right motor: backward
}

void stopMotors() {
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
}

void setup() {
  Serial.begin(9600);
  Wire.begin();

  pinMode(TRIG_LEFT, OUTPUT);
  pinMode(ECHO_LEFT, INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  laser.setTimeout(500);
  if (!laser.init()) {
    Serial.println("LAS:ERR");
  } else {
    laser.startContinuous();
  }

  mpu.initialize();
  if (!mpu.testConnection()) {
    Serial.println("GYR:ERR");
  }
}

void loop() {
  float left  = readUS(TRIG_LEFT, ECHO_LEFT);
  float right = readUS(TRIG_RIGHT, ECHO_RIGHT);
  uint16_t laserMm = laser.readRangeContinuousMillimeters() / 10.0;
  if (laser.timeoutOccurred()) laserMm = 6553;

  int16_t ax, ay, az, gx, gy, gz;
  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

  float pitch = atan2(-ax, sqrt((float)ay*ay + (float)az*az)) * 180.0 / PI;
  float roll  = atan2(ay, az) * 180.0 / PI;

  Serial.print("USL:"); Serial.print(left);
  Serial.print(" USR:"); Serial.print(right);
  Serial.print(" LAS:"); Serial.print(laserMm);
  Serial.print(" PITCH:"); Serial.print(pitch, 1);
  Serial.print(" ROLL:"); Serial.println(roll, 1);

  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'F')      moveForward();
    else if (cmd == 'L') moveLeft();
    else if (cmd == 'R') moveRight();
    else if (cmd == 'S') stopMotors();
  }

  delay(100);
}
