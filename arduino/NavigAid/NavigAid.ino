#define TRIG_LEFT 7
#define ECHO_LEFT 6
#define TRIG_RIGHT 3
#define ECHO_RIGHT 2

#define IN1 8
#define IN2 9
#define IN3 10
#define IN4 11

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
  digitalWrite(IN1, LOW);  digitalWrite(IN2, LOW);   // left motor: stop
  digitalWrite(IN3, LOW);  digitalWrite(IN4, HIGH);  // right motor: forward
}

void moveRight() {
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);   // left motor: forward
  digitalWrite(IN3, LOW);  digitalWrite(IN4, LOW);   // right motor: stop
}

void stopMotors() {
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
}

void setup() {
  Serial.begin(9600);

  pinMode(TRIG_LEFT, OUTPUT);
  pinMode(ECHO_LEFT, INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
}

void loop() {
  float left  = readUS(TRIG_LEFT, ECHO_LEFT);
  float right = readUS(TRIG_RIGHT, ECHO_RIGHT);

  Serial.print("USL:"); Serial.print(left);
  Serial.print(" USR:"); Serial.println(right);

  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'F')      moveForward();
    else if (cmd == 'L') moveLeft();
    else if (cmd == 'R') moveRight();
    else if (cmd == 'S') stopMotors();
  }

  delay(100);
}
